import { getRankImage } from "../../../assets";
import { MAX_SELECTED_RANKS, RANK_LIST } from "../../../data/ranks";
import { PickerPopover } from "./PickerPopover";
import { IconChip } from "./IconChip";

// Picks up to two ranks (a range); `selected` is "Gold_I,Diamond_II".
export function RankPicker({ selected, onChange }) {
  const selectedValues = selected
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const selectedSet = new Set(selectedValues);

  function toggleRank(rankName) {
    if (selectedSet.has(rankName)) {
      onChange(selectedValues.filter((value) => value !== rankName).join(","));
      return;
    }
    if (selectedValues.length >= MAX_SELECTED_RANKS) {
      return;
    }
    onChange([...selectedValues, rankName].join(","));
  }

  const selectedIcons = selectedValues.map((rankName) => {
    const icon = getRankImage(rankName);
    return icon ? <img key={rankName} src={icon} alt={rankName.replace(/_/g, " ")} className="size-5 object-contain" /> : null;
  });

  return (
    <PickerPopover
      label="Rank"
      selectedIcons={selectedIcons}
      onClear={selectedValues.length > 0 ? () => onChange("") : null}
      menuClassName="min-w-[320px] max-w-[min(560px,calc(100vw-24px))]"
    >
      {RANK_LIST.map((rankName) => (
        <IconChip
          key={rankName}
          size="rank"
          label={rankName.replace(/_/g, " ")}
          icon={getRankImage(rankName)}
          fallback={rankName[0]}
          active={selectedSet.has(rankName)}
          onClick={() => toggleRank(rankName)}
        />
      ))}
    </PickerPopover>
  );
}
