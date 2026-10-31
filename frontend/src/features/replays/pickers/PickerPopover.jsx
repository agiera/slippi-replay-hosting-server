import { useCallback, useRef, useState } from "react";

import { ChevronDownIcon, XMarkIcon } from "../../../components/ui/icons";
import { useDismiss } from "../../../components/ui/useDismiss";
import { cn } from "../../../lib/cn";

/**
 * Sidebar field that shows the current picks and opens a chip menu on click.
 * The menu opens to the right of the sidebar on desktop and below the field
 * on narrower layouts (where the sidebar is a drawer).
 */
export function PickerPopover({ label, selectedIcons, onClear, children }) {
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
          "flex min-h-9 items-center rounded-md bg-white/5 outline-1 -outline-offset-1",
          open ? "outline-2 -outline-offset-2 outline-indigo-500" : "outline-white/10 hover:bg-white/10",
        )}
      >
        <button
          ref={triggerRef}
          type="button"
          aria-expanded={open}
          aria-label={label}
          onClick={() => setOpen((prev) => !prev)}
          className="flex min-h-9 min-w-0 flex-1 cursor-pointer flex-wrap items-center gap-1 rounded-md py-1 pr-2 pl-3 text-left text-sm text-gray-400 focus-visible:outline-offset-0"
        >
          {hasSelection ? selectedIcons : <span>Any</span>}
          {onClear ? null : <ChevronDownIcon className="ml-auto size-4 shrink-0" />}
        </button>
        {onClear ? (
          <button
            type="button"
            className="mr-1 flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-gray-400 hover:bg-white/10 hover:text-white"
            onClick={onClear}
          >
            <span className="sr-only">Clear {label.toLowerCase()}</span>
            <XMarkIcon className="size-4" />
          </button>
        ) : null}
      </div>
      {open ? (
        <div
          role="group"
          aria-label={label}
          className={cn(
            "absolute z-30 flex w-72 flex-wrap gap-1 overflow-auto rounded-md bg-gray-800 p-2 shadow-lg ring-1 ring-white/10",
            "top-full left-0 mt-1 max-h-60 lg:top-0 lg:left-full lg:mt-0 lg:ml-4 lg:max-h-72",
          )}
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
