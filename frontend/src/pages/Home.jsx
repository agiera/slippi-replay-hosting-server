import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fetchReplayFiles, fetchReplayFilterOptions, fetchStreamStatus } from "../lib/api";
import crownImage from "../assets/images/crown.png";

const PAGE_SIZE = 40;
const STREAM_SOURCE_STALE_MS = 5 * 60 * 1000;
const STREAM_EVENT_ROW_LIMIT = 20;
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

function renderPlayerCell(file, index) {
  const info = index === 1 ? file.player_1_info : file.player_2_info;
  const fallbackName = index === 1 ? file.player_1 : file.player_2;
  const port = info?.port ?? index;
  const characterImage = getCharacterStock(info?.character_id, info?.character_color);
  const rankImage = getRankImage(info?.rank);
  const rating = info?.rating ?? "--";
  const displayName = info?.name || fallbackName || "-";
  const connectCode = info?.connect_code || "-";
  const isWinner = info?.is_winner === 1;

  return (
    <div className="player-cell">
      <div className="player-name-wrap">
        <div className="player-name">{displayName}</div>
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

function streamPreviewName(player) {
  if (!player) return null;
  return player.display_name || player.tag || player.slippi_code || null;
}

function streamEventStatusLabel(status) {
  switch ((status || "").toLowerCase()) {
    case "completed":
      return "Upload Completed";
    case "failed":
      return "Upload Failed";
    case "incomplete":
      return "Upload Incomplete";
    case "abandoned":
      return "Disconnected Before Upload";
    case "started":
      return "Stream Started";
    default:
      return "Streaming";
  }
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
  const [streamAutoRefreshPaused, setStreamAutoRefreshPaused] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());
  const sentinelRef = useRef(null);

  const streamSourceRows = useMemo(
    () =>
      (streamStatus.sources || [])
        .filter((source) => {
          if (source.connected) {
            return true;
          }
          const updatedAt = source.updated_at ? new Date(source.updated_at).getTime() : NaN;
          if (Number.isNaN(updatedAt)) {
            return false;
          }
          return nowMs - updatedAt <= STREAM_SOURCE_STALE_MS;
        })
        .map((source) => {
          const preview = Array.isArray(source.player_preview) ? source.player_preview : [];
          const p1 = preview.find((player) => Number(player?.port) === 1) || preview[0] || null;
          const p2 = preview.find((player) => Number(player?.port) === 2) || preview[1] || null;
          const p1Name = streamPreviewName(p1) || source.source_name;
          const p2Name = streamPreviewName(p2) || source.username;
          const startedAt = source.updated_at ? new Date(source.updated_at).getTime() : NaN;
          const gameDuration = Number.isNaN(startedAt) ? null : Math.max(0, Math.floor((nowMs - startedAt) / 1000));
          return {
            id: null,
            _streaming: true,
            _streamKind: "source",
            _streamConnected: Boolean(source.connected),
            _streamKey: `${source.source_name}-${source.username}`,
            player_1: p1Name,
            player_2: p2Name,
            player_1_info: p1
              ? {
                  name: p1Name,
                  connect_code: p1.slippi_code || "-",
                  port: Number(p1.port) || 1,
                  rank: p1.rank || null,
                  rating: p1.rating ?? null,
                }
              : null,
            player_2_info: p2
              ? {
                  name: p2Name,
                  connect_code: p2.slippi_code || "-",
                  port: Number(p2.port) || 2,
                  rank: p2.rank || null,
                  rating: p2.rating ?? null,
                }
              : null,
            stage: null,
            game_duration: gameDuration,
            datetime_played: source.updated_at || null,
            stream_source_name: source.source_name,
            stream_repositories: source.repositories || [],
            resolved_tournament_name: source.resolved_tournament_name || null,
            name: `live:${source.source_name}`,
          };
        }),
    [streamStatus.sources, nowMs]
  );

  const streamSourceByName = useMemo(() => {
    const byName = new Map();
    for (const source of streamStatus.sources || []) {
      if (source?.source_name) {
        byName.set(source.source_name, source);
      }
    }
    return byName;
  }, [streamStatus.sources]);

  const streamEventRows = useMemo(() => {
    const events = Array.isArray(streamStatus.events) ? streamStatus.events : [];
    return events.slice(0, STREAM_EVENT_ROW_LIMIT).map((event) => {
      const source = streamSourceByName.get(event.source_name) || null;
      const preview = Array.isArray(source?.player_preview) ? source.player_preview : [];
      const p1 = preview.find((player) => Number(player?.port) === 1) || preview[0] || null;
      const p2 = preview.find((player) => Number(player?.port) === 2) || preview[1] || null;
      const p1Name = streamPreviewName(p1) || event.source_name || "-";
      const p2Name = streamPreviewName(p2) || event.username || "-";

      return {
        id: null,
        _streaming: true,
        _streamEvent: true,
        _streamKind: "event",
        _streamStatus: event.status,
        _streamKey: `${event.source_name}-${event.timestamp}-${event.status}-${event.filename || ""}`,
        player_1: p1Name,
        player_2: p2Name,
        player_1_info: p1
          ? {
              name: p1Name,
              connect_code: p1.slippi_code || "-",
              port: Number(p1.port) || 1,
              rank: p1.rank || null,
              rating: p1.rating ?? null,
            }
          : null,
        player_2_info: p2
          ? {
              name: p2Name,
              connect_code: p2.slippi_code || "-",
              port: Number(p2.port) || 2,
              rank: p2.rank || null,
              rating: p2.rating ?? null,
            }
          : null,
        stage: null,
        game_duration: null,
        datetime_played: event.timestamp || null,
        stream_source_name: event.source_name,
        stream_repositories: event.repository ? [event.repository] : [],
        resolved_tournament_name: event.resolved_tournament_name || null,
        stream_event_filename: event.filename || "",
        name: `event:${event.source_name}`,
      };
    });
  }, [streamStatus.events, streamSourceByName]);

  const tableRows = useMemo(
    () => [...streamSourceRows, ...streamEventRows, ...files],
    [streamSourceRows, streamEventRows, files]
  );

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

  useEffect(() => {
    let active = true;
    let timer = null;

    async function refreshOnce() {
      try {
        const data = await fetchStreamStatus();
        if (active) {
          setStreamStatus(data);
          setStreamError("");
          setStreamAutoRefreshPaused(false);
        }
      } catch (err) {
        if (active) {
          setStreamError(`${err.message || "Failed to load stream status"}. Auto-refresh paused.`);
          setStreamAutoRefreshPaused(true);
        }
      } finally {
        // Stream rows refresh independently from replay file loading state.
      }
    }

    async function refreshLoop() {
      await refreshOnce();
      if (!active || streamAutoRefreshPaused) {
        return;
      }
      timer = setTimeout(refreshLoop, 4000);
    }

    refreshLoop();

    return () => {
      active = false;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [streamAutoRefreshPaused]);

  useEffect(() => {
    const timerId = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => clearInterval(timerId);
  }, []);

  useEffect(() => {
    async function loadFirstPage() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchReplayFiles({
          ...debouncedFilters,
          limit: PAGE_SIZE,
        });
        setFiles(data.items);
        setCursor(data.next_cursor);
        setHasMore(data.next_cursor !== null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadFirstPage();
  }, [debouncedFilters]);

  useEffect(() => {
    if (!sentinelRef.current) {
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting || loading || !hasMore) {
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
          setFiles((prev) => [...prev, ...data.items]);
          setCursor(data.next_cursor);
          setHasMore(data.next_cursor !== null);
        } catch (err) {
          setError(err.message);
        } finally {
          setLoading(false);
        }
      }

      loadMore();
    });

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [debouncedFilters, cursor, hasMore, loading]);

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

  async function onRetryStreamConnection() {
    setStreamAutoRefreshPaused(false);
    setStreamError("");
    try {
      const data = await fetchStreamStatus();
      setStreamStatus(data);
    } catch (err) {
      setStreamError(`${err.message || "Failed to load stream status"}. Auto-refresh paused.`);
      setStreamAutoRefreshPaused(true);
    }
  }

  function filterByStreamSource(sourceName) {
    setFilters((prev) => ({ ...prev, source: sourceName || "" }));
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
                    <td colSpan={5}>No files found.</td>
                  </tr>
                )}
                {tableRows.map((file) => {
                  const isStreamingRow = Boolean(file._streaming);
                  const isStreamEventRow = Boolean(file._streamEvent);
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
                    ? (
                      isStreamEventRow
                        ? `${file.stream_source_name || "-"} - ${streamEventStatusLabel(file._streamStatus)}`
                        : (file.stream_source_name || "-")
                    )
                    : (file.source_name || file.collection_name || folderMeta.source || "-");
                  const streamBadgeLabel = isStreamEventRow
                    ? "EVENT"
                    : file._streamConnected
                      ? "LIVE"
                      : "RECENT";
                  return (
                  <tr
                    key={
                      isStreamingRow
                        ? `stream-${file._streamKey}`
                        : `${file.name}-${file.datetime_played || "unknown"}-${file.player_1 || "p1"}`
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
                    <td>{renderPlayerCell(file, 1)}</td>
                    <td>{renderPlayerCell(file, 2)}</td>
                    <td>
                      <div className="row-game-stack">
                        <div className="row-game-stage">
                          {isStreamingRow
                            ? (isStreamEventRow ? streamEventStatusLabel(file._streamStatus) : "Streaming")
                            : formatStageName(file.stage)}
                        </div>
                        <div className="row-game-duration">{formatGameDuration(file.game_duration)}</div>
                        <div className="row-game-date">{formatPlayedDateTime(file.datetime_played)}</div>
                      </div>
                    </td>
                    <td>
                      <div className="viewer-row-actions">
                        {isStreamingRow ? (
                          <>
                            <button
                              type="button"
                              className="viewer-row-btn viewer-row-btn-secondary"
                              onClick={() => filterByStreamSource(file.stream_source_name)}
                            >
                              Filter Source
                            </button>
                            <button
                              type="button"
                              className="viewer-row-btn viewer-row-btn-secondary"
                              onClick={() => void onRetryStreamConnection()}
                            >
                              Refresh Stream
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
