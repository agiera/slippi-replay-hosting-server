import { useCallback, useRef, useState } from "react";

import { useDismiss } from "../../../components/ui/useDismiss";
import { cn } from "../../../lib/cn";

/**
 * Sidebar field that shows the current picks and opens a chip menu on click.
 * The menu opens to the right of the sidebar on desktop and below the field
 * on narrower layouts (where the sidebar is a drawer).
 */
export function PickerPopover({ label, selectedIcons, onClear, menuClassName, children }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);

  const close = useCallback((reason) => {
    setOpen(false);
    if (reason === "escape") {
      triggerRef.current?.focus();
    }
  }, []);
  useDismiss(rootRef, open, close);

  const hasSelection = selectedIcons.length > 0;

  return (
    <div ref={rootRef} className="relative">
      <div
        className={cn(
          "flex min-h-9 items-center rounded-lg border bg-surface-soft text-[0.88rem]",
          open ? "border-accent-strong" : "border-accent/35 hover:border-accent-strong",
        )}
      >
        <button
          ref={triggerRef}
          type="button"
          aria-expanded={open}
          aria-label={label}
          onClick={() => setOpen((prev) => !prev)}
          className="flex min-h-9 min-w-0 flex-1 cursor-pointer flex-wrap items-center gap-1 rounded-lg px-2.5 py-1 text-left text-muted"
        >
          {hasSelection ? selectedIcons : <span>Any</span>}
        </button>
        {onClear ? (
          <button
            type="button"
            className="mr-1 flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted hover:bg-accent/20 hover:text-fg"
            onClick={onClear}
            aria-label={`Clear ${label.toLowerCase()}`}
          >
            <span aria-hidden="true">✕</span>
          </button>
        ) : null}
      </div>
      {open ? (
        <div
          role="group"
          aria-label={label}
          className={cn(
            "absolute z-30 flex w-max min-w-[260px] max-w-[min(520px,calc(100vw-32px))] flex-wrap gap-1 overflow-auto",
            "rounded-[10px] border border-accent/35 bg-panel/97 p-2 shadow-[0_8px_28px_rgb(0_0_0/0.55)] backdrop-blur-sm",
            "top-[calc(100%+4px)] left-0 max-h-[240px] lg:top-0 lg:left-[calc(100%+20px)] lg:max-h-[300px]",
            menuClassName,
          )}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
