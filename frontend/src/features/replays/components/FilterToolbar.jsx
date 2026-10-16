import { Button } from "../../../components/ui/Button";
import { describeActiveFilters } from "../filters";

/**
 * Row above the replay list: the "Filters" drawer button (narrow layouts only)
 * and one removable chip per active filter. Renders nothing on desktop when no
 * filters are set.
 */
export function FilterToolbar({ filters, onOpenFilters, onRemoveFilter, onClearAll }) {
  const activeFilters = describeActiveFilters(filters);
  const hasFilters = activeFilters.length > 0;

  return (
    <div className={hasFilters ? "mb-3 flex flex-wrap items-center gap-1.5" : "mb-3 flex lg:hidden"}>
      <Button variant="secondary" size="sm" className="gap-1.5 text-fg lg:hidden" onClick={onOpenFilters}>
        Filters
        {hasFilters ? (
          <span className="rounded-full bg-accent px-1.5 text-[0.72rem] leading-[1.15rem] tabular-nums">
            {activeFilters.length}
          </span>
        ) : null}
      </Button>

      {hasFilters ? (
        <>
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label="Active filters">
            {activeFilters.map(({ key, label }) => (
              <li key={key}>
                <span className="inline-flex items-center rounded-full border border-accent/40 bg-accent/14 py-0.5 pr-0.5 pl-2.5 text-[0.8rem] font-medium text-subtle">
                  {label}
                  <button
                    type="button"
                    onClick={() => onRemoveFilter(key)}
                    aria-label={`Remove filter: ${label}`}
                    className="ml-1 flex size-5 cursor-pointer items-center justify-center rounded-full text-[0.7rem] text-muted hover:bg-accent/40 hover:text-fg"
                  >
                    <span aria-hidden="true">✕</span>
                  </button>
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={onClearAll}
            className="cursor-pointer rounded px-1.5 text-[0.8rem] font-semibold text-muted underline-offset-2 hover:text-fg hover:underline"
          >
            Clear all
          </button>
        </>
      ) : null}
    </div>
  );
}
