import { useEffect, useRef } from "react";

import { Button } from "../../../components/ui/Button";
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
      {open ? <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" aria-hidden="true" /> : null}
      <aside
        ref={panelRef}
        aria-label="Filters"
        className={cn(
          "lg:sticky lg:z-[2] lg:block lg:top-[calc(var(--top-nav-height)+var(--top-nav-border)+var(--top-filter-height)+var(--main-grid-gap-from-filter)+var(--sidebar-sticky-nudge))]",
          open
            ? "max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:z-50 max-lg:w-[min(320px,88vw)] max-lg:overflow-y-auto max-lg:border-r max-lg:border-accent/35 max-lg:bg-surface max-lg:p-4"
            : "hidden",
        )}
      >
        <div className="mb-3 flex items-center justify-between lg:hidden">
          <h2 className="m-0 text-base font-semibold">Filters</h2>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>

        <form className="grid gap-4" onSubmit={(event) => event.preventDefault()}>
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

          <label className="flex cursor-pointer items-center gap-2 text-[0.88rem] text-subtle">
            <input
              name="include_handwarmers"
              type="checkbox"
              className="m-0 size-4 accent-accent-strong"
              checked={filters.include_handwarmers === "1"}
              onChange={(event) => setFilter("include_handwarmers", event.target.checked ? "1" : "")}
            />
            Include hand warmers
          </label>

          <Button variant="ghost" size="sm" className="w-full" onClick={resetFilters}>
            Clear all
          </Button>
        </form>
      </aside>
    </>
  );
}

function FieldGroup({ legend, children }) {
  return (
    <fieldset className="m-0 grid min-w-0 gap-2 border-0 p-0">
      <legend className="mb-1.5 p-0 text-[0.8rem] font-semibold text-muted">{legend}</legend>
      {children}
    </fieldset>
  );
}
