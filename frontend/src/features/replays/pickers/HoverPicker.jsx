import { cn } from "../../../lib/cn";

/**
 * Sidebar field that shows the current picks and opens a chip menu on hover or
 * focus. The menu opens to the right on desktop and below on narrower layouts.
 */
export function HoverPicker({ label, selectedIcons, onClear, menuClassName, children }) {
  return (
    <div className="group relative flex flex-col">
      <div
        className={cn(
          "flex flex-1 select-none flex-wrap items-center gap-1.5 rounded-lg border border-accent/35",
          "bg-surface-soft px-2.5 py-1.5 text-[0.88rem] text-muted",
        )}
      >
        {selectedIcons.length > 0 ? (
          <div className="flex max-w-full flex-wrap items-center gap-[3px]">{selectedIcons}</div>
        ) : null}
        <span>{label}</span>
        {onClear ? (
          <button
            type="button"
            className="ml-auto cursor-pointer border-0 bg-transparent px-0.5 text-[0.8rem] leading-none text-muted hover:text-fg"
            onClick={(event) => {
              event.stopPropagation();
              onClear();
            }}
            aria-label={`Clear ${label || "selection"}`}
          >
            ✕
          </button>
        ) : null}
      </div>
      <div
        className={cn(
          "absolute z-20 hidden w-max min-w-[260px] max-w-[min(520px,calc(100vw-24px))] flex-wrap gap-1 overflow-auto",
          "rounded-[10px] border border-accent/35 bg-panel/97 p-2 shadow-[0_8px_28px_rgb(0_0_0/0.55)] backdrop-blur-sm",
          "group-focus-within:flex group-hover:flex",
          "top-[calc(100%+4px)] left-0 max-h-[220px] lg:top-0 lg:left-full lg:max-h-[260px]",
          // Invisible bridge over the gap so the menu stays open while the pointer crosses it.
          "before:absolute before:-top-2 before:inset-x-0 before:h-2",
          "lg:before:inset-y-0 lg:before:right-auto lg:before:-left-3 lg:before:h-auto lg:before:w-3",
          menuClassName,
        )}
      >
        {children}
      </div>
    </div>
  );
}
