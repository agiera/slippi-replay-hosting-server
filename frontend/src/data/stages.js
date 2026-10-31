export const STAGE_NAME_BY_ID = {
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

// Break the Targets stages share a single image.
export const TARGET_STAGE_ID_MIN = 33;
export const TARGET_STAGE_ID_MAX = 58;

export function isTargetStage(stageId) {
  return stageId >= TARGET_STAGE_ID_MIN && stageId <= TARGET_STAGE_ID_MAX;
}
