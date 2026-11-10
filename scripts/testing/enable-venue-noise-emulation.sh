#!/usr/bin/env bash
# Emulate the Nov 3 venue Wi-Fi for Wiis behind the Slate: ~275 ms RTT, 5.7% uplink / 1.6% ACK loss.
set -euo pipefail

SLATE=${SLATE:-100.102.146.120}
DEV=${DEV:-tailscale0}
# Correlated loss ("loss X% 25%") dropped ~nothing on kernel 7.2; keep it uncorrelated.
ACK_LOSS=${ACK_LOSS:-1.6%}
DATA_LOSS=${DATA_LOSS:-5.7%}

"$(dirname "$0")/disable-venue-noise-emulation.sh" 2>/dev/null || true

# server -> Wii (ACKs): only the Slate's traffic goes to band 4 with netem
sudo tc qdisc add dev "$DEV" root handle 1: prio bands 4 priomap 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
sudo tc qdisc add dev "$DEV" parent 1:4 handle 40: netem delay 130ms 50ms distribution normal loss random "$ACK_LOSS"
sudo tc filter add dev "$DEV" parent 1: protocol ip u32 match ip dst "$SLATE/32" flowid 1:4

# Wii -> server (data): redirect the Slate's incoming packets through ifb0 and shape them there
sudo modprobe ifb numifbs=1
sudo ip link set ifb0 up
sudo tc qdisc add dev "$DEV" handle ffff: ingress
sudo tc filter add dev "$DEV" parent ffff: protocol ip u32 match ip src "$SLATE/32" action mirred egress redirect dev ifb0
sudo tc qdisc add dev ifb0 root netem delay 130ms 50ms distribution normal loss random "$DATA_LOSS" rate 1mbit

sudo tc -s qdisc show dev "$DEV"
sudo tc -s qdisc show dev ifb0
