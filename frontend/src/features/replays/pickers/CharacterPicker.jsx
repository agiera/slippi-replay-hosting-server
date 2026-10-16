import { getCharacterStock } from "../../../assets";
import { CHARACTER_LIST } from "../../../data/characters";
import { parseSelectedCharacterIds } from "../filters";
import { PickerPopover } from "./PickerPopover";
import { IconChip } from "./IconChip";

// `selected` / `onChange` use the comma-separated character id format ("2,9").
export function CharacterPicker({ selected, onChange }) {
  const selectedIds = new Set(parseSelectedCharacterIds(selected));
  const selectedChars = CHARACTER_LIST.filter((character) => selectedIds.has(character.id));

  function toggleCharacter(id) {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onChange(Array.from(next).sort((a, b) => a - b).join(","));
  }

  const selectedIcons = selectedChars.map((character) => {
    const icon = getCharacterStock(character.id, 0);
    return icon ? (
      <img
        key={character.id}
        src={icon}
        alt={character.name}
        className="size-5 object-contain [image-rendering:pixelated]"
      />
    ) : null;
  });

  return (
    <PickerPopover
      label="Characters"
      selectedIcons={selectedIcons}
      onClear={selectedChars.length > 0 ? () => onChange("") : null}
    >
      {CHARACTER_LIST.map(({ id, name }) => (
        <IconChip
          key={id}
          label={name}
          icon={getCharacterStock(id, 0)}
          fallback={name[0]}
          active={selectedIds.has(id)}
          onClick={() => toggleCharacter(id)}
        />
      ))}
    </PickerPopover>
  );
}
