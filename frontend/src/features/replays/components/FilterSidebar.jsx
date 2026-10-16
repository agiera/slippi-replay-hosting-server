import { useEffect, useRef } from "react";

import { Button } from "../../../components/ui/Button";
import { XMarkIcon } from "../../../components/ui/icons";
import { Input } from "../../../components/ui/Input";
import { useDismiss } from "../../../components/ui/useDismiss";
import { cn } from "../../../lib/cn";
import { parseSelectedCharacterIds } from "../filters";
import { CharacterPicker } from "../pickers/CharacterPicker";
import { CostumePicker } from "../pickers/CostumePicker";
import { RankPicker } from "../pickers/RankPicker";

/**
 * Replay filters. A sticky sidebar on desktop; below the `lg` breakpoint it is
 * hidden until `open`, then shown as a drawer from the left.
 */
export function FilterSidebar({ filters, setFilter, setCharacters, resetFilters, open, onClose }) {
  const panelRef = useRef(null);
  useDismiss(panelRef, open, onClose);

  // Lock page scroll behind the drawer and move focus into it.
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    panelRef.current?.querySelector("input")?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const bindInput = (name) => ({
    name,
    size: "sm",
    value: filters[name],
    onChange: (event) => setFilter(name, event.target.value),
  });

  return (
    <>
      {open ? <div className="fixed inset-0 z-40 bg-gray-950/75 lg:hidden" aria-hidden="true" /> : null}
      <aside
        ref={panelRef}
        aria-label="Filters"
        className={cn(
          // Sticky offset: nav (h-14) + collections bar (h-16) + the page's top padding (py-6).
          "lg:sticky lg:top-36 lg:z-10 lg:block",
          open
            ? "max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-50 max-lg:w-full max-lg:max-w-xs max-lg:overflow-y-auto max-lg:bg-gray-900 max-lg:p-4 max-lg:shadow-xl max-lg:ring-1 max-lg:ring-white/10"
            : "hidden",
        )}
      >
        <div className="mb-4 flex items-center justify-between lg:hidden">
          <h2 className="text-lg font-semibold text-white">Filters</h2>
          <button
            type="button"
            onClick={onClose}
            className="-mr-2 flex size-10 cursor-pointer items-center justify-center rounded-md text-gray-400 hover:bg-white/5 hover:text-white"
          >
            <span className="sr-only">Close filters</span>
            <XMarkIcon className="size-5" />
          </button>
        </div>

        <form className="space-y-6" onSubmit={(event) => event.preventDefault()}>
          <FieldGroup legend="Search">
            <Input placeholder="Keyword" aria-label="Keyword" {...bindInput("keyword")} />
            <Input placeholder="Player name or code" aria-label="Player" {...bindInput("player")} />
          </FieldGroup>

          <FieldGroup legend="Characters">
            <CharacterPicker selected={filters.character} onChange={setCharacters} />
            <CostumePicker
              selectedCharacters={parseSelectedCharacterIds(filters.character)}
              selectedCostumes={filters.costume}
              onChange={(value) => setFilter("costume", value)}
            />
          </FieldGroup>

          <FieldGroup legend="Rank and rating">
            <RankPicker selected={filters.rank} onChange={(value) => setFilter("rank", value)} />
            <div className="grid grid-cols-2 gap-2">
              <Input type="number" min="0" step="1" placeholder="Min" aria-label="Minimum rating" {...bindInput("min_rank")} />
              <Input type="number" min="0" step="1" placeholder="Max" aria-label="Maximum rating" {...bindInput("max_rank")} />
            </div>
          </FieldGroup>

          <FieldGroup legend="Played between">
            <div className="grid grid-cols-2 gap-2">
              <Input type="date" aria-label="From date" className="px-2" {...bindInput("date_from")} />
              <Input type="date" aria-label="To date" className="px-2" {...bindInput("date_to")} />
            </div>
          </FieldGroup>

          <label className="flex cursor-pointer items-center gap-3 text-sm text-gray-300">
            <input
              name="include_handwarmers"
              type="checkbox"
              className="size-4 cursor-pointer rounded-sm accent-indigo-500"
              checked={filters.include_handwarmers === "1"}
              onChange={(event) => setFilter("include_handwarmers", event.target.checked ? "1" : "")}
            />
            Include hand warmers
          </label>

          <Button variant="secondary" className="w-full" onClick={resetFilters}>
            Clear all
          </Button>
        </form>
      </aside>
    </>
  );
}

function FieldGroup({ legend, children }) {
  return (
    <fieldset className="grid min-w-0 gap-2">
      <legend className="mb-2 text-sm/6 font-medium text-white">{legend}</legend>
      {children}
    </fieldset>
  );
}
