import { MultiSelect } from "../../../components/ui/MultiSelect";

// Sticky bar under the nav with the repository / tournament / source pickers.
export function TopFilterBar({ filters, options, setFilter }) {
  return (
    <section
      className={
        // `relative` (not static) on narrow layouts so z-index lifts the dropdowns above the sidebar.
        "relative z-[9] -mx-2 w-[calc(100%+16px)] border-t border-b border-t-accent/14 border-b-accent/35 " +
        "bg-[rgb(8_7_12/0.9)] px-2 py-2.5 backdrop-blur-md " +
        "lg:sticky lg:top-[calc(var(--top-nav-height)+var(--top-nav-border))]"
      }
    >
      <div className="mx-auto grid w-[min(1080px,100%)] grid-cols-1 gap-2 md:grid-cols-3">
        <MultiSelect
          label="Repository"
          selected={filters.repository}
          options={options.repositories}
          onChange={(value) => setFilter("repository", value)}
        />
        <MultiSelect
          label="Tournament"
          selected={filters.tournament}
          options={options.tournaments}
          onChange={(value) => setFilter("tournament", value)}
        />
        <MultiSelect
          label="Source"
          selected={filters.source}
          options={options.sources}
          onChange={(value) => setFilter("source", value)}
        />
      </div>
    </section>
  );
}
