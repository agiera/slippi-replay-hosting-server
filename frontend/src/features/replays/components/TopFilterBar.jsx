import { MultiSelect } from "../../../components/ui/MultiSelect";

// Bar under the nav with the repository / tournament / source pickers. Sticky
// (and a fixed h-16) from `lg`, which the sidebar's sticky offset relies on.
export function TopFilterBar({ filters, options, setFilter }) {
  return (
    <section
      aria-label="Collections"
      className="relative z-20 border-b border-white/10 bg-gray-950/80 py-3 backdrop-blur lg:sticky lg:top-14 lg:flex lg:h-16 lg:items-center"
    >
      <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-2 px-4 sm:px-6 md:grid-cols-3 lg:px-8">
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
