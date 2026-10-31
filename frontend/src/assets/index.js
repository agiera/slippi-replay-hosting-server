// Image lookups backed by Vite globs. Vite-only: keep this out of modules that
// run under `node --test`.
import { isTargetStage } from "../data/stages.js";

export { default as crownImage } from "./images/crown.png";

const STAGE_IMAGES = import.meta.glob("./images/stages/*.png", {
  eager: true,
  import: "default",
});
const CHARACTER_STOCK_IMAGES = import.meta.glob("./images/characters/*/*/stock.png", {
  eager: true,
  import: "default",
});
const RANK_IMAGES = import.meta.glob("./images/ranks/*.svg", {
  eager: true,
  import: "default",
});
const PORT_ICONS = import.meta.glob("./icons/*.svg", {
  eager: true,
  import: "default",
});

// Character id -> sorted costume ids that have a stock icon on disk.
const COSTUME_IDS_BY_CHARACTER = (() => {
  const map = new Map();
  const pathPattern = /\.\/images\/characters\/(\d+)\/(\d+)\/stock\.png$/;

  Object.keys(CHARACTER_STOCK_IMAGES).forEach((assetPath) => {
    const match = pathPattern.exec(assetPath);
    if (!match) {
      return;
    }

    const characterId = Number(match[1]);
    const costumeId = Number(match[2]);
    if (!map.has(characterId)) {
      map.set(characterId, new Set());
    }
    map.get(characterId).add(costumeId);
  });

  map.forEach((costumeIds, characterId) => {
    map.set(characterId, Array.from(costumeIds).sort((a, b) => a - b));
  });

  return map;
})();

export function getCostumeIds(characterId) {
  return COSTUME_IDS_BY_CHARACTER.get(characterId) || [0];
}

export function getStageImage(stageId) {
  if (stageId === null || stageId === undefined) {
    return "";
  }

  const normalizedId = Number(stageId);
  if (Number.isNaN(normalizedId)) {
    return "";
  }

  if (isTargetStage(normalizedId)) {
    return STAGE_IMAGES["./images/stages/targets.png"] || "";
  }

  return STAGE_IMAGES[`./images/stages/${normalizedId}.png`] || "";
}

export function getCharacterStock(characterId, costumeId = 0) {
  if (characterId === null || characterId === undefined) {
    return "";
  }

  const normalizedColor = Number.isInteger(Number(costumeId)) ? Number(costumeId) : 0;
  const directPath = `./images/characters/${characterId}/${normalizedColor}/stock.png`;
  if (CHARACTER_STOCK_IMAGES[directPath]) {
    return CHARACTER_STOCK_IMAGES[directPath];
  }

  return CHARACTER_STOCK_IMAGES[`./images/characters/${characterId}/0/stock.png`] || "";
}

export function getRankImage(rankValue) {
  const normalizedRank = (rankValue || "Unranked1").replace(/\s+/g, "_");
  return RANK_IMAGES[`./images/ranks/rank_${normalizedRank}.svg`] || "";
}

// Port slot icon: the coloured badge for the player's own port, grey otherwise.
export function getPortIcon(activePort, slot) {
  if (Number(activePort) === slot) {
    return PORT_ICONS[`./icons/port${slot}.svg`] || "";
  }
  return PORT_ICONS["./icons/noport.svg"] || "";
}
