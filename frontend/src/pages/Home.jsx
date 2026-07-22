import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fetchReplayFiles, fetchReplayFilterOptions, fetchStreamStatus, openStreamEvents } from "../lib/api";
import crownImage from "../assets/images/crown.png";

const PAGE_SIZE = 40;
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
const STAGE_IMAGES = import.meta.glob("../assets/images/stages/*.png", {
  eager: true,
  import: "default",
});
const CHARACTER_STOCK_IMAGES = import.meta.glob("../assets/images/characters/*/*/stock.png", {
  eager: true,
  import: "default",
});
const RANK_IMAGES = import.meta.glob("../assets/images/ranks/*.svg", {
  eager: true,
  import: "default",
});
const PORT_ICONS = import.meta.glob("../assets/icons/*.svg", {
  eager: true,
  import: "default",
});

// Character id -> name, matching peppi_py character_id values (Melee roster)
const CHARACTER_LIST = [
  { id: 0, name: "Captain Falcon" },
  { id: 1, name: "Donkey Kong" },
  { id: 2, name: "Fox" },
  { id: 3, name: "Mr. Game & Watch" },
  { id: 4, name: "Kirby" },
  { id: 5, name: "Bowser" },
  { id: 6, name: "Link" },
  { id: 7, name: "Luigi" },
  { id: 8, name: "Mario" },
  { id: 9, name: "Marth" },
  { id: 10, name: "Mewtwo" },
  { id: 11, name: "Ness" },
  { id: 12, name: "Peach" },
  { id: 13, name: "Pikachu" },
  { id: 14, name: "Ice Climbers" },
  { id: 15, name: "Jigglypuff" },
  { id: 16, name: "Samus" },
  { id: 17, name: "Yoshi" },
  { id: 18, name: "Zelda" },
  { id: 19, name: "Sheik" },
  { id: 20, name: "Falco" },
  { id: 21, name: "Young Link" },
  { id: 22, name: "Dr. Mario" },
  { id: 23, name: "Roy" },
  { id: 24, name: "Pichu" },
  { id: 25, name: "Ganondorf" },
  { id: 31, name: "Master Hand" },
  { id: 32, name: "Wireframe M" },
];

const STAGE_NAME_BY_ID = {
  2: "Fountain of Dreams",
  3: "Pokemon Stadium",
  4: "Peach's Castle",
  5: "Kongo Jungle",
  6: "Brinstar",
  7: "Corneria",
  8: "Yoshi's Story",
  9: "Onett",
  10: "Mute City",
  11: "Rainbow Cruise",
  12: "Jungle Japes",
  13: "Great Bay",
  14: "Hyrule Temple",
  15: "Brinstar Depths",
  16: "Yoshi's Island",
  17: "Green Greens",
  18: "Fourside",
  19: "Mushroom Kingdom I",
  20: "Mushroom Kingdom II",
  22: "Venom",
  23: "Poke Floats",
  24: "Big Blue",
  25: "Icicle Mountain",
  26: "Icetop",
  27: "Flat Zone",
  28: "Dream Land N64",
  29: "Yoshi's Island N64",
  30: "Kongo Jungle N64",
  31: "Battlefield",
  32: "Final Destination",
};

const INITIAL_FILTERS = {
  keyword: "",
  character: "",
  ranked: "",
  rank: "",
  min_rank: "",
  max_rank: "",
  player: "",
  repository: "",
  tournament: "",
  source: "",
  include_handwarmers: "",
  date_from: "",
  date_to: "",
};

const RANK_FILTER_LIST = [
  "Unranked1",
  "Unranked2",
  "Unranked3",
  "Bronze_I",
  "Bronze_II",
  "Bronze_III",
  "Silver_I",
  "Silver_II",
  "Silver_III",
  "Gold_I",
  "Gold_II",
  "Gold_III",
  "Platinum_I",
  "Platinum_II",
  "Platinum_III",
  "Diamond_I",
  "Diamond_II",
  "Diamond_III",
  "Master_I",
  "Master_II",
  "Master_III",
  "Grand_Master",
];

const SLIPPILAB_URL = (import.meta.env.VITE_SLIPPILAB_URL || "http://localhost:4173").replace(/\/$/, "");

function SearchableMultiSelect({ label, selected, options, onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef(null);

  const selectedValues = new Set(
    selected
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean)
  );

  const filteredOptions = options.filter((option) => option.toLowerCase().includes(query.toLowerCase().trim()));

  useEffect(() => {
    function handleDocumentClick(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    return () => document.removeEventListener("mousedown", handleDocumentClick);
  }, []);

  function toggleValue(value) {
    const next = new Set(selectedValues);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    onChange(Array.from(next).join(","));
  }

  const selectedArray = Array.from(selectedValues);
  const summary = selectedArray.length === 0
    ? "All"
    : selectedArray.length <= 2
      ? selectedArray.join(", ")
      : `${selectedArray.length} selected`;

  return (
    <div className="search-multiselect" ref={rootRef}>
      <button
        type="button"
        className={`search-multiselect-trigger${open ? " open" : ""}`}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="search-multiselect-label">{label}</span>
        <span className="search-multiselect-value">{summary}</span>
      </button>
      {open ? (
        <div className="search-multiselect-panel">
          <input
            className="search-multiselect-input"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${label.toLowerCase()}`}
          />
          <div className="search-multiselect-options">
            {filteredOptions.map((option) => {
              const isSelected = selectedValues.has(option);
              return (
                <button
                  type="button"
                  key={option}
                  className={`search-multiselect-option${isSelected ? " selected" : ""}`}
                  onClick={() => toggleValue(option)}
                >
                  <span>{isSelected ? "☑" : "☐"}</span>
                  <span>{option}</span>
                </button>
              );
            })}
            {filteredOptions.length === 0 ? (
              <div className="search-multiselect-empty">No matches</div>
            ) : null}
          </div>
          {selectedValues.size > 0 ? (
            <button type="button" className="search-multiselect-clear" onClick={() => onChange("")}>Clear</button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function CharacterPicker({ selected, onChange }) {
  const selectedIds = new Set(
    selected
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean)
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value))
  );
  const selectedChars = CHARACTER_LIST.filter((c) => selectedIds.has(c.id));

  function toggleCharacter(id) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    const nextValue = Array.from(next).sort((a, b) => a - b).join(",");
    onChange(nextValue);
  }

  return (
    <div className="char-picker-wrap">
      <div className="char-picker-label">
        {selectedChars.length > 0 ? (
          <div className="char-picker-selected-list">
            {selectedChars.map((char) => {
              const selectedImg = getCharacterStock(char.id, 0);
              return selectedImg ? (
                <img
                  key={char.id}
                  src={selectedImg}
                  alt={char.name}
                  className="char-picker-selected-icon"
                />
              ) : null;
            })}
          </div>
        ) : null}
        <span>{selectedChars.length > 0 ? `${selectedChars.length} selected` : "Character"}</span>
        {selectedChars.length > 0 ? (
          <button
            type="button"
            className="char-picker-clear"
            onClick={(e) => {
              e.stopPropagation();
              onChange("");
            }}
            aria-label="Clear"
          >
            ✕
          </button>
        ) : null}
      </div>
      <div className="char-picker">
        {CHARACTER_LIST.map(({ id, name }) => {
          const img = getCharacterStock(id, 0);
          const active = selectedIds.has(id);
          return (
            <button
              key={id}
              type="button"
              title={name}
              className={`char-chip${active ? " active" : ""}`}
              onClick={() => toggleCharacter(id)}
            >
              {img ? <img src={img} alt={name} /> : <span>{name[0]}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function RankPicker({ selected, onChange }) {
  const selectedValues = selected
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const selectedSet = new Set(selectedValues);

  function toggleRank(rankName) {
    if (selectedSet.has(rankName)) {
      const next = selectedValues.filter((value) => value !== rankName);
      onChange(next.join(","));
      return;
    }
    if (selectedValues.length >= 2) {
      return;
    }
    onChange([...selectedValues, rankName].join(","));
  }

  return (
    <div className="char-picker-wrap">
      <div className="char-picker-label">
        {selectedValues.length > 0 ? (
          <div className="char-picker-selected-list">
            {selectedValues.map((rankName) => {
              const rankImage = getRankImage(rankName);
              return rankImage ? (
                <img key={rankName} src={rankImage} alt={rankName} className="rank-picker-selected-icon" />
              ) : null;
            })}
          </div>
        ) : null}
        <span>{selectedValues.length > 0 ? `${selectedValues.length} selected` : "Rank"}</span>
        {selectedValues.length > 0 ? (
          <button
            type="button"
            className="char-picker-clear"
            onClick={(e) => {
              e.stopPropagation();
              onChange("");
            }}
            aria-label="Clear"
          >
            ✕
          </button>
        ) : null}
      </div>
      <div className="char-picker rank-picker-menu">
        {RANK_FILTER_LIST.map((rankName) => {
          const rankImage = getRankImage(rankName);
          const active = selectedSet.has(rankName);
          return (
            <button
              key={rankName}
              type="button"
              title={rankName}
              className={`char-chip rank-chip${active ? " active" : ""}`}
              onClick={() => toggleRank(rankName)}
            >
              {rankImage ? <img src={rankImage} alt={rankName} /> : <span>{rankName[0]}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function parseFiltersFromSearch(searchParams) {
  return {
    keyword: searchParams.get("keyword") || "",
    character: searchParams.get("character") || "",
    ranked: searchParams.get("ranked") || "",
    rank: searchParams.get("rank") || "",
    min_rank: searchParams.get("min_rank") || "",
    max_rank: searchParams.get("max_rank") || "",
    player: searchParams.get("player") || "",
    repository: searchParams.get("repository") || "",
    tournament: searchParams.get("tournament") || "",
    source: searchParams.get("source") || searchParams.get("collection") || "",
    include_handwarmers: searchParams.get("include_handwarmers") || "",
    date_from: searchParams.get("date_from") || "",
    date_to: searchParams.get("date_to") || "",
  };
}

function buildSearchParams(filters) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  return params;
}

function normalizeStreamStatusPayload(payload, fallbackEvents = []) {
  const normalizedSources = (Array.isArray(payload?.sources) ? payload.sources : []).map((source) => {
    const normalizedPreview = (Array.isArray(source?.player_preview) ? source.player_preview : []).map((player) => {
      const connectCode = player?.connect_code || player?.slippi_code || null;
      const name = player?.name || player?.display_name || player?.tag || connectCode || null;
      return {
        name,
        connect_code: connectCode,
        character_id: player?.character_id ?? null,
        character_color: player?.character_color ?? null,
        port: player?.port ?? null,
        type: player?.type ?? null,
        is_cpu: Boolean(player?.is_cpu),
        is_winner: player?.is_winner ?? null,
        rank: player?.rank ?? null,
        rating: player?.rating ?? null,
      };
    });

    return {
      ...source,
      player_preview: normalizedPreview,
    };
  });

  return {
    tournament: payload?.tournament || null,
    sources: normalizedSources,
    events: Array.isArray(payload?.events) ? payload.events : fallbackEvents,
  };
}

function formatGameDuration(totalSeconds) {
  if (totalSeconds === null || totalSeconds === undefined) {
    return "-";
  }

  const seconds = Math.max(0, Number(totalSeconds) || 0);
  const minutesPart = Math.floor(seconds / 60);
  const secondsPart = seconds % 60;
  return `${minutesPart}m${secondsPart}s`;
}

function formatPlayedDateTime(value) {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const month = date.toLocaleString("en-US", { month: "short" });
  const day = date.getDate();
  const year = date.getFullYear();
  let hours = date.getHours();
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const period = hours >= 12 ? "pm" : "am";
  hours = hours % 12 || 12;

  return `${month} ${day}, ${year} - ${hours}:${minutes}${period}`;
}

function getStageImage(stageId) {
  if (stageId === null || stageId === undefined) {
    return "";
  }

  const normalizedId = Number(stageId);
  if (Number.isNaN(normalizedId)) {
    return "";
  }

  if (normalizedId >= 33 && normalizedId <= 58) {
    return STAGE_IMAGES["../assets/images/stages/targets.png"] || "";
  }

  return STAGE_IMAGES[`../assets/images/stages/${normalizedId}.png`] || "";
}

function formatStageName(stageId) {
  if (stageId === null || stageId === undefined) {
    return "-";
  }

  const normalizedId = Number(stageId);
  if (Number.isNaN(normalizedId)) {
    return String(stageId);
  }

  return STAGE_NAME_BY_ID[normalizedId] || `Stage ${normalizedId}`;
}

function parseFolderMetadata(folder) {
  if (!folder) {
    return { repository: null, source: null };
  }

  const parts = String(folder)
    .split("/")
    .filter(Boolean);
  if (parts.length === 0) {
    return { repository: null, source: null };
  }

  if (parts[0] === "uploads") {
    const repository = parts[1] || null;
    let source = null;
    if (parts[2]) {
      const maybeSource = parts[2];
      if (!(maybeSource.length === 4 && /^\d+$/.test(maybeSource))) {
        source = maybeSource;
      }
    }
    return { repository, source };
  }

  return {
    repository: parts[0] || null,
    source: parts[1] || null,
  };
}

function getResolvedTournamentName(file) {
  return (
    file?.resolved_tournament_name ||
    file?.current_tournament_name ||
    file?.tournament_name ||
    file?.tournament ||
    null
  );
}

function getStageRowStyle(stageId) {
  const stageImage = getStageImage(stageId);
  if (!stageImage) {
    return undefined;
  }

  return {
    backgroundImage: [
      "linear-gradient(to right, rgba(18, 16, 29, 0.95) 18%, rgba(18, 16, 29, 0.62) 36%, rgba(18, 16, 29, 0.62) 64%, rgba(18, 16, 29, 0.95) 82%)",
      "radial-gradient(circle at left center, rgba(107, 92, 177, 0.44), transparent 44%)",
      "radial-gradient(circle at right center, rgba(107, 92, 177, 0.44), transparent 44%)",
      `url(${stageImage})`,
    ].join(","),
    backgroundRepeat: "no-repeat, no-repeat, no-repeat, no-repeat",
    backgroundPosition: "center, left center, right center, center",
    backgroundSize: "auto, 440px 180%, 440px 180%, 980px auto",
  };
}

function getCharacterStock(characterId, color = 0) {
  if (characterId === null || characterId === undefined) {
    return "";
  }

  const normalizedColor = Number.isInteger(Number(color)) ? Number(color) : 0;
  const directPath = `../assets/images/characters/${characterId}/${normalizedColor}/stock.png`;
  if (CHARACTER_STOCK_IMAGES[directPath]) {
    return CHARACTER_STOCK_IMAGES[directPath];
  }

  const fallbackPath = `../assets/images/characters/${characterId}/0/stock.png`;
  return CHARACTER_STOCK_IMAGES[fallbackPath] || "";
}

function getRankImage(rankValue) {
  const normalizedRank = (rankValue || "Unranked1").replace(/\s+/g, "_");
  return RANK_IMAGES[`../assets/images/ranks/rank_${normalizedRank}.svg`] || "";
}

function getPortIcon(activePort, slot) {
  const normalizedActive = Number(activePort);
  if (normalizedActive === slot) {
    return PORT_ICONS[`../assets/icons/port${slot}.svg`] || "";
  }
  return PORT_ICONS["../assets/icons/noport.svg"] || "";
}

// Renders a single player cell. Both live-stream rows and completed replay rows
// produce the same normalized player shape, so they share this one renderer.
function renderPlayerCell(player) {
  // Empty padded slot (e.g. a live row with fewer players than the column count):
  // render a blank cell instead of fabricating a port badge for a non-existent player.
  if (!player) {
    return <div className="player-cell player-cell-empty" />;
  }

  const info = player;
  const port = info.port ?? null;
  const characterImage = getCharacterStock(info.character_id, info.character_color);
  const rankImage = getRankImage(info.rank);
  const rating = info.rating ?? "--";
  const displayName = info.name || info.display_name || info.tag || info.connect_code || "-";
  const connectCode = info.connect_code || "-";
  const isWinner = info.is_winner === 1;
  const isCpu = Boolean(info.is_cpu) || Number(info.type) === 1;

  return (
    <div className="player-cell">
      <div className="player-name-wrap">
        <div className="player-name">{displayName}{isCpu ? " [CPU]" : ""}</div>
        {isWinner ? <img src={crownImage} alt="Winner" className="player-winner-crown" /> : null}
      </div>
      <div className="player-connect-code">{connectCode}</div>
      <div className="player-meta-row">
        <div className="player-meta-item">
          {characterImage ? <img src={characterImage} alt="Character" className="player-character-icon" /> : "-"}
        </div>
        <div className="player-meta-item">
          {rankImage ? <img src={rankImage} alt="Rank" className="player-rank-icon" /> : "-"}
        </div>
        <div className="player-rating">{rating}</div>
      </div>
      <div className="player-ports">
        {[1, 2, 3, 4].map((slot) => {
          const icon = getPortIcon(port, slot);
          return icon ? <img key={slot} src={icon} alt={`Port ${slot}`} className="player-port-icon" /> : null;
        })}
      </div>
    </div>
  );
}

// Returns the players for a row, sorted by port. Both live-stream rows and
// completed replay rows expose a normalized `players` array, so this is the
// single source of truth the table renders from. The player_1_info/player_2_info
// pair is only a legacy fallback for rows missing the array.
function getRowPlayers(file) {
  const players = Array.isArray(file?.players) ? file.players : [];
  const normalized = players
    .filter((player) => player && typeof player === "object")
    .slice()
    .sort((a, b) => {
      const pa = Number(a?.port);
      const pb = Number(b?.port);
      if (!Number.isFinite(pa) && !Number.isFinite(pb)) return 0;
      if (!Number.isFinite(pa)) return 1;
      if (!Number.isFinite(pb)) return -1;
      return pa - pb;
    });

  if (normalized.length > 0) {
    return normalized;
  }

  return [
    file?.player_1_info ? { ...file.player_1_info, name: file.player_1_info.name || file.player_1 } : null,
    file?.player_2_info ? { ...file.player_2_info, name: file.player_2_info.name || file.player_2 } : null,
  ].filter(Boolean);
}

export default function Home() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialFromUrl = parseFiltersFromSearch(searchParams);
  const [filters, setFilters] = useState(initialFromUrl);
  const [debouncedFilters, setDebouncedFilters] = useState(initialFromUrl);
  const [files, setFiles] = useState([]);
  const [repoOptions, setRepoOptions] = useState([]);
  const [tournamentOptions, setTournamentOptions] = useState([]);
  const [sourceOptions, setSourceOptions] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [streamStatus, setStreamStatus] = useState({ tournament: null, sources: [], events: [] });
  const [streamError, setStreamError] = useState("");
  const [nowMs, setNowMs] = useState(Date.now());
  const sentinelRef = useRef(null);
  const latestCompletedEventMsRef = useRef(0);

  const streamSourceRows = useMemo(
    () =>
      (streamStatus.sources || [])
        // Show a source once its partial SLP has produced a player preview.
        // Keep a just-disconnected source visible until its finalized upload row
        // appears, avoiding a brief visual gap between live and final rows.
        .filter(
          (source) => {
            if (source.connected) {
              return true;
            }

            if (!Array.isArray(source.player_preview) || source.player_preview.length === 0) {
              return false;
            }

            const sourceName = (source.source_name || "").trim();
            if (!sourceName) {
              return false;
            }

            const connectedAtMs = source.connected_at ? new Date(source.connected_at).getTime() : NaN;
            const terminalEventForSession = (streamStatus.events || []).some((event) => {
              if ((event?.source_name || "").trim() !== sourceName) {
                return false;
              }

              const status = String(event?.status || "").toLowerCase();
              if (!["ended", "completed", "abandoned", "incomplete", "failed"].includes(status)) {
                return false;
              }

              if (Number.isNaN(connectedAtMs)) {
                return true;
              }

              const eventMs = event?.timestamp ? new Date(event.timestamp).getTime() : NaN;
              return !Number.isNaN(eventMs) && eventMs >= connectedAtMs - 5000;
            });

            // If this source session already emitted a terminal event, hide the
            // live row even when the finalized replay row is filtered out.
            if (terminalEventForSession) {
              return false;
            }

            const hasFinalizedRowForSession = files.some((file) => {
              const fileSource = (file?.source_name || file?.collection_name || "").trim();
              if (!fileSource || fileSource !== sourceName) {
                return false;
              }

              if (Number.isNaN(connectedAtMs)) {
                return true;
              }

              const birthMs = file?.birth_time ? new Date(file.birth_time).getTime() : NaN;
              if (Number.isNaN(birthMs)) {
                return false;
              }

              // Allow slight skew around session connect time when matching the
              // newly finalized row that replaces this live row.
              return birthMs >= connectedAtMs - 5000;
            });

            return !hasFinalizedRowForSession;
          },
        )
        .map((source) => {
          // The stream-status API already returns player_preview in the same
          // normalized shape as completed replays' `players`, so both row types
          // flow through getRowPlayers/renderPlayerCell identically.
          const players = Array.isArray(source.player_preview) ? source.player_preview : [];
          const connectedAtMs = source.connected_at ? new Date(source.connected_at).getTime() : NaN;
          const updatedAtMs = source.updated_at ? new Date(source.updated_at).getTime() : NaN;
          const lastActivityAtMs = source.last_activity_at ? new Date(source.last_activity_at).getTime() : NaN;
          const endAtMs = !Number.isNaN(lastActivityAtMs)
            ? lastActivityAtMs
            : updatedAtMs;
          const durationBaseMs = !Number.isNaN(connectedAtMs)
            ? connectedAtMs
            : (!Number.isNaN(updatedAtMs) ? updatedAtMs : lastActivityAtMs);
          const durationNowMs = source.connected ? nowMs : endAtMs;
          const playedAt = source.connected_at || source.updated_at || source.last_activity_at || null;
          const gameDuration = Number.isNaN(durationBaseMs) || Number.isNaN(durationNowMs)
            ? 0
            : Math.max(0, Math.floor((durationNowMs - durationBaseMs) / 1000));
          return {
            id: null,
            _streaming: true,
            _streamKind: "source",
            _streamConnected: Boolean(source.connected),
            _streamKey: `${source.source_name}-${source.username}`,
            players,
            stage: source.stage_preview ?? null,
            game_duration: gameDuration,
            datetime_played: playedAt,
            stream_source_name: source.source_name,
            stream_repositories: source.repositories || [],
            resolved_tournament_name: source.resolved_tournament_name || null,
            name: `live:${source.source_name}`,
          };
        }),
    [streamStatus.sources, streamStatus.events, files, nowMs]
  );

  const tableRows = useMemo(
    () => [...streamSourceRows, ...files],
    [streamSourceRows, files]
  );

  const tablePlayerColumnCount = useMemo(() => {
    const maxPlayers = tableRows.reduce((maxCount, row) => Math.max(maxCount, getRowPlayers(row).length), 0);
    return Math.min(4, Math.max(2, maxPlayers));
  }, [tableRows]);

  useEffect(() => {
    const nextFilters = parseFiltersFromSearch(searchParams);
    const nextString = JSON.stringify(nextFilters);
    const currentString = JSON.stringify(filters);
    if (nextString !== currentString) {
      setFilters(nextFilters);
      setDebouncedFilters(nextFilters);
    }
  }, [searchParams]);

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      setDebouncedFilters(filters);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [filters]);

  useEffect(() => {
    const nextParams = buildSearchParams(debouncedFilters);
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [debouncedFilters, searchParams, setSearchParams]);

  useEffect(() => {
    let cancelled = false;

    async function loadFilterOptions() {
      try {
        const data = await fetchReplayFilterOptions();
        if (cancelled) {
          return;
        }
        setRepoOptions(Array.isArray(data.repositories) ? data.repositories : []);
        setTournamentOptions(Array.isArray(data.tournaments) ? data.tournaments : []);
        setSourceOptions(Array.isArray(data.sources) ? data.sources : []);
      } catch {
        if (!cancelled) {
          setRepoOptions([]);
          setTournamentOptions([]);
          setSourceOptions([]);
        }
      }
    }

    loadFilterOptions();

    return () => {
      cancelled = true;
    };
  }, []);

  const loadFirstPage = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchReplayFiles({
        ...debouncedFilters,
        limit: PAGE_SIZE,
      });
      const nextCursor = data?.next_cursor ?? null;
      setFiles(data.items);
      setCursor(nextCursor);
      setHasMore(nextCursor !== null);
    } catch (err) {
      setError(err.message);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  }, [debouncedFilters]);

  useEffect(() => {
    let active = true;

    function maybeRefreshReplayList(events) {
      const refreshStatuses = new Set(["pending_parse", "slippi_file_metadata", "ended", "completed"]);
      const refreshEvents = (events || []).filter((event) => {
        const status = (event?.status || "").toLowerCase();
        return refreshStatuses.has(status);
      });
      const newestRefreshEventMs = refreshEvents.reduce((latest, event) => {
        const ts = event?.timestamp ? new Date(event.timestamp).getTime() : NaN;
        if (Number.isNaN(ts)) {
          return latest;
        }
        return Math.max(latest, ts);
      }, 0);

      if (newestRefreshEventMs > latestCompletedEventMsRef.current) {
        latestCompletedEventMsRef.current = newestRefreshEventMs;
        void loadFirstPage();
      }
    }

    const stream = openStreamEvents((event) => {
      if (!active) {
        return;
      }

      if (event.type === "snapshot" || event.type === "status") {
        try {
          const payload = JSON.parse(event.data || "{}");
          setStreamStatus((prev) =>
            normalizeStreamStatusPayload(payload, Array.isArray(prev?.events) ? prev.events : [])
          );
          setStreamError("");
          if (event.type === "snapshot") {
            maybeRefreshReplayList(payload?.events || []);
          }
        } catch {
          setStreamError("Failed to parse stream status update");
        }
        return;
      }

      if (event.type === "heartbeat") {
        return;
      }

      if (event.type === "stream_event") {
        try {
          const payload = JSON.parse(event.data || "{}");
          setStreamStatus((prev) => {
            const nextEvents = [payload, ...(prev?.events || [])]
              .filter((row, index, rows) => {
                const id = Number(row?.event_id) || 0;
                if (!id) {
                  return true;
                }
                return rows.findIndex((candidate) => (Number(candidate?.event_id) || 0) === id) === index;
              })
              .slice(0, 200);
            return {
              tournament: prev?.tournament || null,
              sources: Array.isArray(prev?.sources) ? prev.sources : [],
              events: nextEvents,
            };
          });
          // Some environments intermittently miss `status` frames while still
          // receiving `stream_event`. Re-sync sources from the status endpoint
          // on each event so live rows appear/update without manual refresh.
          void fetchStreamStatus()
            .then((statusPayload) => {
              if (!active) {
                return;
              }
              setStreamStatus((prev) =>
                normalizeStreamStatusPayload(statusPayload, Array.isArray(prev?.events) ? prev.events : [])
              );
            })
            .catch(() => {
              // Keep the existing SSE-driven state when status fetch fails.
            });
          setStreamError("");
          maybeRefreshReplayList([payload]);
        } catch {
          setStreamError("Failed to parse stream event update");
        }
        return;
      }
    });

    stream.onerror = () => {
      if (!active) {
        return;
      }
      setStreamError("Stream updates disconnected. Reconnecting...");
    };

    return () => {
      active = false;
      stream.close();
    };
  }, [loadFirstPage]);

  useEffect(() => {
    const timerId = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  useEffect(() => {
    void loadFirstPage();
  }, [loadFirstPage]);

  useEffect(() => {
    if (!sentinelRef.current) {
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting || loading || !hasMore || error) {
        return;
      }

      async function loadMore() {
        setLoading(true);
        setError("");
        try {
          const data = await fetchReplayFiles({
            ...debouncedFilters,
            limit: PAGE_SIZE,
            cursor,
          });
          const nextCursor = data?.next_cursor ?? null;
          setFiles((prev) => [...prev, ...data.items]);
          setCursor(nextCursor);
          // Stop auto-pagination if server does not provide a cursor or repeats it.
          setHasMore(nextCursor !== null && nextCursor !== cursor);
        } catch (err) {
          setError(err.message);
          setHasMore(false);
        } finally {
          setLoading(false);
        }
      }

      loadMore();
    });

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [debouncedFilters, cursor, hasMore, loading, error]);

  function onFilterChange(e) {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  }

  function onResetFilters() {
    setFilters(INITIAL_FILTERS);
  }

  const isInitialLoading = loading && files.length === 0;

  async function openViewerInNewTab(fileId) {
    if (!fileId) {
      return;
    }
    const replayUrl = new URL(`${API_BASE.replace(/\/+$/, "")}/replays/files/${fileId}/download`);

    setError("");
    const viewerUrl = `${SLIPPILAB_URL}?replayUrl=${encodeURIComponent(replayUrl.toString())}`;
    window.open(viewerUrl, "_blank", "noopener,noreferrer");
  }

  function downloadReplay(fileId) {
    if (!fileId) {
      return;
    }
    const replayUrl = new URL(`${API_BASE.replace(/\/+$/, "")}/replays/files/${fileId}/download`);
    window.open(replayUrl.toString(), "_blank", "noopener,noreferrer");
  }

  function openInSlippi(fileId) {
    if (!fileId) {
      return;
    }
    const replayUrl = new URL(`${API_BASE.replace(/\/+$/, "")}/replays/files/${fileId}/download`);
    window.location.href = `slippi://play?path=${encodeURIComponent(replayUrl.toString())}`;
  }

  function streamInSlippi(sourceName) {
    const normalizedSource = (sourceName || "").trim();
    if (!normalizedSource) {
      return;
    }

    const latestSourceReplay = files.find(
      (item) => (item.source_name || item.collection_name || "") === normalizedSource
    );
    const replayId = latestSourceReplay?.id ?? latestSourceReplay?._id;

    // Keep the source filter in sync with the stream action.
    setFilters((prev) => ({ ...prev, source: normalizedSource }));

    if (replayId) {
      openInSlippi(replayId);
      return;
    }

    setStreamError(`No replay available yet for source ${normalizedSource}.`);
  }

  return (
    <main className="home-layout">
      <section className="top-filter-menu">
        <div className="top-filter-inner">
          <SearchableMultiSelect
            label="Repository"
            selected={filters.repository}
            options={repoOptions}
            onChange={(value) => setFilters((prev) => ({ ...prev, repository: value }))}
          />
          <SearchableMultiSelect
            label="Tournament"
            selected={filters.tournament}
            options={tournamentOptions}
            onChange={(value) => setFilters((prev) => ({ ...prev, tournament: value }))}
          />
          <SearchableMultiSelect
            label="Source"
            selected={filters.source}
            options={sourceOptions}
            onChange={(value) => setFilters((prev) => ({ ...prev, source: value }))}
          />
        </div>
      </section>

      <div className="home-main-grid">
        <aside className="filter-sidebar">
          <form className="filter-sidebar-form">
            <input name="keyword" placeholder="Keyword" value={filters.keyword} onChange={onFilterChange} />
            <CharacterPicker
              selected={filters.character}
              onChange={(val) => setFilters((prev) => ({ ...prev, character: val }))}
            />
            <RankPicker
              selected={filters.rank}
              onChange={(val) => setFilters((prev) => ({ ...prev, rank: val }))}
            />
            <input
              name="min_rank"
              type="number"
              min="0"
              step="1"
              placeholder="Min rating"
              value={filters.min_rank}
              onChange={onFilterChange}
            />
            <input
              name="max_rank"
              type="number"
              min="0"
              step="1"
              placeholder="Max rating"
              value={filters.max_rank}
              onChange={onFilterChange}
            />
            <input name="player" placeholder="Player" value={filters.player} onChange={onFilterChange} />
            <label className="filter-checkbox-row">
              <input
                name="include_handwarmers"
                type="checkbox"
                checked={filters.include_handwarmers === "1"}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    include_handwarmers: e.target.checked ? "1" : "",
                  }))
                }
              />
              Include hand warmers
            </label>
            <input name="date_from" type="date" value={filters.date_from} onChange={onFilterChange} />
            <input name="date_to" type="date" value={filters.date_to} onChange={onFilterChange} />
            <button type="button" className="filter-btn ghost" onClick={onResetFilters}>
              Reset
            </button>
          </form>
        </aside>

        <section className="home-panel">

        {error && <p className="error">{error}</p>}

        {!error && (
          <div className="file-table-wrap">
            <table className="file-table">
              <tbody>
                {isInitialLoading &&
                  Array.from({ length: 6 }).map((_, idx) => (
                    <tr key={`loading-${idx}`} className="file-row-loading">
                      <td>
                        <div className="shimmer-line shimmer-line-mid" />
                      </td>
                      <td>
                        <div className="shimmer-line shimmer-line-wide" />
                      </td>
                      <td>
                        <div className="shimmer-line shimmer-line-wide" />
                      </td>
                      <td>
                        <div className="shimmer-line shimmer-line-mid" />
                      </td>
                      <td>
                        <div className="shimmer-line shimmer-line-short" />
                      </td>
                    </tr>
                  ))}

                {!isInitialLoading && tableRows.length === 0 && (
                  <tr>
                    <td colSpan={tablePlayerColumnCount + 3}>No files found.</td>
                  </tr>
                )}
                {tableRows.map((file) => {
                  const isStreamingRow = Boolean(file._streaming);
                  const fileId = file.id ?? file._id;
                  const folderMeta = parseFolderMetadata(file.folder);
                  const resolvedTournamentName = getResolvedTournamentName(file);
                  const repoTournamentLabel = isStreamingRow
                    ? (
                      resolvedTournamentName ||
                      streamStatus?.tournament?.current_tournament_name ||
                      streamStatus?.tournament?.name ||
                      streamStatus?.tournament?.repository_name ||
                      file.stream_repositories?.[0] ||
                      folderMeta.repository ||
                      "Streaming"
                    )
                    : (resolvedTournamentName || folderMeta.repository || "-");
                  const sourceLabel = isStreamingRow
                    ? "Live stream"
                    : (file.source_name || file.collection_name || folderMeta.source || "-");
                  const streamBadgeLabel = "LIVE";
                  const rowPlayers = getRowPlayers(file).slice(0, tablePlayerColumnCount);
                  const paddedPlayers = [
                    ...rowPlayers,
                    ...Array.from({ length: Math.max(0, tablePlayerColumnCount - rowPlayers.length) }, () => null),
                  ];
                  // Player, stage and start-datetime are populated the same way for
                  // live and completed rows; only a stage placeholder differs while a
                  // live game has no stage parsed yet.
                  const startDateTime = file.datetime_played || file.birth_time;
                  const stageLabel = file.stage !== null && file.stage !== undefined
                    ? formatStageName(file.stage)
                    : (isStreamingRow ? "Streaming" : formatStageName(file.stage));
                  return (
                  <tr
                    key={
                      isStreamingRow
                        ? `stream-${file._streamKey}`
                        : `${file.name}-${file.datetime_played || "unknown"}-${rowPlayers[0]?.name || "p1"}`
                    }
                    className="stage-row"
                    style={getStageRowStyle(file.stage)}
                  >
                    <td>
                      <div className="row-meta-cell">
                        {isStreamingRow ? (
                          <span className="live-pill">
                            <span className="live-dot" aria-hidden="true" />
                            {streamBadgeLabel}
                          </span>
                        ) : null}
                        <div className="row-meta-primary">{repoTournamentLabel}</div>
                        <div className="row-meta-secondary">{sourceLabel}</div>
                      </div>
                    </td>
                    {paddedPlayers.map((player, idx) => (
                      <td key={`player-col-${idx}`}>{renderPlayerCell(player)}</td>
                    ))}
                    <td>
                      <div className="row-game-stack">
                        <div className="row-game-stage">{stageLabel}</div>
                        <div className="row-game-duration">{formatGameDuration(file.game_duration)}</div>
                        <div className="row-game-date">{formatPlayedDateTime(startDateTime)}</div>
                      </div>
                    </td>
                    <td>
                      <div className="viewer-row-actions">
                        {isStreamingRow ? (
                          <>
                            <button
                              type="button"
                              className="viewer-row-btn viewer-row-btn-secondary"
                              onClick={() => streamInSlippi(file.stream_source_name)}
                            >
                              Stream in Slippi
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="viewer-row-btn"
                              onClick={() => openInSlippi(fileId)}
                              disabled={!fileId}
                            >
                              View in Slippi
                            </button>
                            <button
                              type="button"
                              className="viewer-row-btn"
                              onClick={() => void openViewerInNewTab(fileId)}
                              disabled={!fileId}
                            >
                              View on SlippiLab
                            </button>
                            <button
                              type="button"
                              className="viewer-row-btn"
                              onClick={() => downloadReplay(fileId)}
                              disabled={!fileId}
                            >
                              Download
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {streamError && <p className="error">{streamError}</p>}

        <div ref={sentinelRef} className="scroll-sentinel" />
        {loading && files.length > 0 && <p>Loading more...</p>}
        {!hasMore && files.length > 0 && <p className="subtitle">End of results.</p>}

        </section>
      </div>
    </main>
  );
}
