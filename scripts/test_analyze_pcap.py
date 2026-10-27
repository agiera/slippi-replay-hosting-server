import unittest
from unittest.mock import patch

from analyze_pcap import FIELDS, Transfer, add_range, analyze, associate_commands, flag_set


def packet(**overrides):
    values = dict.fromkeys(FIELDS, "")
    values.update({
        "frame.time_epoch": "100.0", "frame.len": "1040", "frame.cap_len": "128",
        "tcp.stream": "1", "ip.src": "100.1.1.1", "ip.dst": "100.2.2.2",
        "tcp.srcport": "40000", "tcp.dstport": "22100", "tcp.len": "1000",
        "tcp.seq_raw": "10000", "tcp.ack_raw": "5000", "tcp.flags.syn": "False",
        "tcp.flags.fin": "False", "tcp.flags.reset": "False",
    })
    values.update(overrides)
    return values


class PcapAnalysisTests(unittest.TestCase):
    def test_flag_formats(self):
        for value in ("True", "true", "1"):
            self.assertTrue(flag_set(value))
        for value in ("False", "0", ""):
            self.assertFalse(flag_set(value))

    def test_ranges_merge_and_do_not_double_count(self):
        ranges = []
        self.assertEqual(add_range(ranges, 1000, 2000), 1000)
        self.assertEqual(add_range(ranges, 0, 1500), 1000)
        self.assertEqual(add_range(ranges, 1000, 2000), 0)
        self.assertEqual(ranges, [(0, 2000)])

    def test_transfer_counts_unique_bytes_and_real_flags(self):
        transfer = Transfer(1, "100.1.1.1", 40000, "100.2.2.2", 22100, 100, 100)
        transfer.consume(packet())
        transfer.consume(packet(**{"frame.time_epoch": "100.1", "tcp.analysis.retransmission": "1"}))
        transfer.consume(packet(**{"frame.time_epoch": "100.2", "tcp.seq_raw": "11000", "tcp.flags.fin": "True"}))
        report = transfer.report()
        self.assertEqual(report["unique_bytes"], 2000)
        self.assertEqual(report["repeated_sequence_bytes"], 1000)
        self.assertEqual(report["suspected_retransmitted_packets"], 1)
        self.assertTrue(report["fin_seen"])
        self.assertFalse(report["reset_seen"])
        self.assertFalse(report["syn_seen"])

    def test_sequence_wrap_and_receiver_ack(self):
        transfer = Transfer(1, "100.1.1.1", 40000, "100.2.2.2", 22100, 100, 100)
        transfer.consume(packet(**{"tcp.seq_raw": str((1 << 32) - 500)}))
        transfer.consume(packet(**{"frame.time_epoch": "100.1", "tcp.seq_raw": "500"}))
        transfer.consume(packet(**{
            "frame.time_epoch": "100.101", "ip.src": "100.2.2.2", "ip.dst": "100.1.1.1",
            "tcp.srcport": "22100", "tcp.dstport": "40000", "tcp.len": "0",
            "tcp.ack_raw": "1500", "tcp.window_size": "60000",
        }))
        self.assertEqual(transfer.bytes, 2000)
        self.assertEqual(len(transfer.local_acks), 2)
        self.assertEqual(transfer.windows, [60000])

    def test_trailing_silence_is_not_hidden_by_retransmissions(self):
        transfer = Transfer(1, "100.1.1.1", 40000, "100.2.2.2", 22100, 100, 100)
        transfer.consume(packet())
        transfer.consume(packet(**{"frame.time_epoch": "134", "tcp.analysis.retransmission": "1"}))
        transfer.consume(packet(**{
            "frame.time_epoch": "237", "ip.src": "100.2.2.2", "ip.dst": "100.1.1.1",
            "tcp.srcport": "22100", "tcp.dstport": "40000", "tcp.len": "0", "tcp.flags.fin": "True",
        }))
        report = transfer.report()
        self.assertEqual(report["arrival_gap_ms"]["count"], 0)
        self.assertEqual(report["trailing_no_progress_ms"], 137000)
        self.assertEqual(report["unique_bytes"], 1000)

    def test_zero_window_is_attributed_to_correct_endpoint(self):
        transfer = Transfer(1, "100.1.1.1", 40000, "100.2.2.2", 22100, 100, 100)
        transfer.consume(packet(**{"tcp.analysis.zero_window": "1", "tcp.window_size": "0"}))
        self.assertEqual(transfer.report()["server_tcp_analysis"]["zero_window"], 0)
        transfer.consume(packet(**{
            "frame.time_epoch": "100.1", "ip.src": "100.2.2.2", "ip.dst": "100.1.1.1",
            "tcp.srcport": "22100", "tcp.dstport": "40000", "tcp.len": "0",
            "tcp.analysis.zero_window": "1", "tcp.window_size": "0",
        }))
        self.assertEqual(transfer.report()["server_tcp_analysis"]["zero_window"], 1)

    def test_passive_mapping_matches_host_port_and_time(self):
        transfer = Transfer(1, "100.1.1.1", 40000, "100.2.2.2", 22100, 100, 102)
        stale = Transfer(2, "100.1.1.1", 40001, "100.2.2.2", 22100, 50, 52)
        commands = [
            {"tcp.stream": "3", "frame.time_epoch": "99.5", "ip.src": "100.2.2.2",
             "ip.dst": "100.1.1.1", "ftp.response.arg": "Entering passive mode (100,2,2,2,86,84).",
             "ftp.request.command": "", "ftp.request.arg": ""},
            {"tcp.stream": "3", "frame.time_epoch": "100.1", "ip.src": "100.1.1.1",
             "ip.dst": "100.2.2.2", "ftp.response.arg": "", "ftp.request.command": "STOR",
             "ftp.request.arg": "Game_00244421A1A5_test.Team RN.slp"},
        ]
        associate_commands({1: transfer, 2: stale}, commands)
        self.assertEqual(transfer.filename, commands[1]["ftp.request.arg"])
        self.assertEqual(stale.filename, "")

    @patch("analyze_pcap.tshark_rows")
    @patch("analyze_pcap.log_context", return_value=({}, 0, 50))
    def test_warns_when_log_does_not_cover_capture(self, log_context, tshark_rows):
        tshark_rows.side_effect = [iter([packet()]), iter([])]
        report = analyze("example.pcap", "backend.log")
        self.assertTrue(any("do not overlap" in warning for warning in report["warnings"]))
        self.assertEqual(report["truncated_packets"], 1)

    @patch("analyze_pcap.tshark_rows", side_effect=[iter([]), iter([])])
    def test_no_replay_packets_is_explicit(self, tshark_rows):
        report = analyze("example.pcap")
        self.assertEqual(report["transfers"], [])
        self.assertTrue(any("No matching" in warning for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()