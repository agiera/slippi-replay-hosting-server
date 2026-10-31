import { Button } from "../../../components/ui/Button";
import { FunnelIcon, XMarkIcon } from "../../../components/ui/icons";
import { describeActiveFilters } from "../filters";

/**
 * Row above the replay list: the "Filters" drawer button (narrow layouts only)
 * and one removable badge per active filter. Renders nothing on desktop when no
 * filters are set.
 */
export function FilterToolbar({ filters, onOpenFilters, onRemoveFilter, onClearAll }) {
  const activeFilters = describeActiveFilters(filters);
  const hasFilters = activeFilters.length > 0;

  return (
    <div className={hasFilters ? "mb-4 flex flex-wrap items-center gap-2" : "mb-4 flex lg:hidden"}>
      <Button variant="secondary" size="sm" className="lg:hidden" onClick={onOpenFilters}>
        <FunnelIcon className="size-4 text-gray-400" />
        Filters
        {hasFilters ? (
          <span className="rounded-full bg-indigo-500 px-1.5 text-xs/5 font-semibold tabular-nums">
            {activeFilters.length}
          </span>
        ) : null}
      </Button>

      {hasFilters ? (
        <>
          <ul className="flex flex-wrap gap-2" aria-label="Active filters">
            {activeFilters.map(({ key, label }) => (
              <li key={key}>
                <span className="inline-flex items-center gap-x-0.5 rounded-md bg-gray-400/10 py-1 pr-1 pl-2 text-xs font-medium text-gray-300 ring-1 ring-inset ring-gray-400/20">
                  {label}
                  <button
                    type="button"
                    onClick={() => onRemoveFilter(key)}
                    className="relative ml-0.5 cursor-pointer rounded-sm p-0.5 text-gray-400 hover:bg-gray-500/30 hover:text-white"
                  >
                    <span className="sr-only">Remove filter: {label}</span>
                    <XMarkIcon className="size-3.5" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={onClearAll}
            className="cursor-pointer rounded-md px-1.5 text-sm font-semibold text-indigo-400 hover:text-indigo-300"
          >
            Clear all
          </button>
        </>
      ) : null}
    </div>
  );
}
