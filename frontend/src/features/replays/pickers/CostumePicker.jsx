import { getCharacterStock, getCostumeIds } from "../../../assets";
import { CHARACTER_BY_ID } from "../../../data/characters";
import { cn } from "../../../lib/cn";
import { parseCostumeSelection, serializeCostumeSelection } from "../filters";
import { IconChip } from "./IconChip";

// One row of costume chips per selected character. Disabled until a character is picked.
export function CostumePicker({ selectedCharacters, selectedCostumes, onChange }) {
  const disabled = selectedCharacters.length === 0;
  const selections = parseCostumeSelection(selectedCostumes);

  function toggleCostume(characterId, costumeId) {
    const nextSelections = parseCostumeSelection(selectedCostumes);
    if (!nextSelections.has(characterId)) {
      nextSelections.set(characterId, new Set());
    }

    const characterSelections = nextSelections.get(characterId);
    if (characterSelections.has(costumeId)) {
      characterSelections.delete(costumeId);
    } else {
      characterSelections.add(costumeId);
    }

    if (characterSelections.size === 0) {
      nextSelections.delete(characterId);
    }

    onChange(serializeCostumeSelection(nextSelections));
  }

  return (
    <div
      className={cn(
        "grid gap-2 rounded-lg border border-accent/35 bg-surface-soft p-2",
        disabled && "opacity-55 grayscale-[0.35]",
      )}
    >
      <div className="text-[0.84rem] text-muted">Costume</div>
      {disabled ? null : (
        <div className="grid gap-2">
          {selectedCharacters.map((characterId) => {
            const characterName = CHARACTER_BY_ID.get(characterId)?.name || `Character ${characterId}`;
            const activeCostumes = selections.get(characterId) || new Set();
            return (
              <div key={characterId} className="flex flex-wrap gap-1">
                {getCostumeIds(characterId).map((costumeId) => (
                  <IconChip
                    key={costumeId}
                    size="costume"
                    label={`${characterName} costume ${costumeId + 1}`}
                    icon={getCharacterStock(characterId, costumeId)}
                    fallback={costumeId}
                    active={activeCostumes.has(costumeId)}
                    onClick={() => toggleCostume(characterId, costumeId)}
                  />
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
