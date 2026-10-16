import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { parseSelectedCharacterIds } from "../filters";
import { CharacterPicker } from "../pickers/CharacterPicker";
import { CostumePicker } from "../pickers/CostumePicker";
import { RankPicker } from "../pickers/RankPicker";

export function FilterSidebar({ filters, setFilter, setCharacters, resetFilters }) {
  const bindInput = (name) => ({
    name,
    value: filters[name],
    onChange: (event) => setFilter(name, event.target.value),
  });

  return (
    <aside
      className={
        "z-[2] rounded-[14px] border border-accent/35 bg-surface/88 p-3 " +
        "lg:sticky lg:top-[calc(var(--top-nav-height)+var(--top-nav-border)+var(--top-filter-height)+var(--main-grid-gap-from-filter)+var(--sidebar-sticky-nudge))]"
      }
    >
      <form className="grid grid-cols-2 gap-2 lg:grid-cols-1" onSubmit={(event) => event.preventDefault()}>
        <Input placeholder="Keyword" {...bindInput("keyword")} />
        <CharacterPicker selected={filters.character} onChange={setCharacters} />
        <CostumePicker
          selectedCharacters={parseSelectedCharacterIds(filters.character)}
          selectedCostumes={filters.costume}
          onChange={(value) => setFilter("costume", value)}
        />
        <RankPicker selected={filters.rank} onChange={(value) => setFilter("rank", value)} />
        <Input type="number" min="0" step="1" placeholder="Min rating" {...bindInput("min_rank")} />
        <Input type="number" min="0" step="1" placeholder="Max rating" {...bindInput("max_rank")} />
        <Input placeholder="Player" {...bindInput("player")} />
        <label className="flex items-center gap-2 whitespace-nowrap text-[0.92rem] text-muted">
          <input
            name="include_handwarmers"
            type="checkbox"
            className="m-0"
            checked={filters.include_handwarmers === "1"}
            onChange={(event) => setFilter("include_handwarmers", event.target.checked ? "1" : "")}
          />
          Include hand warmers
        </label>
        <Input type="date" aria-label="From date" {...bindInput("date_from")} />
        <Input type="date" aria-label="To date" {...bindInput("date_to")} />
        <Button variant="ghost" className="mt-3 w-full" onClick={resetFilters}>
          Reset
        </Button>
      </form>
    </aside>
  );
}
