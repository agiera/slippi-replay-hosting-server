import { useEffect, useRef, useState } from "react";

import { cn } from "../../lib/cn";

const splitValues = (value) =>
  value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

/**
 * Dropdown with a search box for picking several string options.
 * `selected` and `onChange` use a comma-separated string, matching the URL format.
 */
export function MultiSelect({ label, selected, options, onChange }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef(null);

  const selectedValues = new Set(splitValues(selected));
  const normalizedQuery = query.toLowerCase().trim();
  const filteredOptions = options.filter((option) => option.toLowerCase().includes(normalizedQuery));

  useEffect(() => {
    function handleDocumentClick(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    return () => document.removeEventListener("mousedown", handleDocumentClick);
  }, []);

  function toggleValue(value) {
    const next = new Set(selectedValues);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    onChange(Array.from(next).join(","));
  }

  const selectedArray = Array.from(selectedValues);
  const summary = selectedArray.length === 0
    ? "All"
    : selectedArray.length <= 2
      ? selectedArray.join(", ")
      : `${selectedArray.length} selected`;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        aria-expanded={open}
        className={cn(
          "flex w-full cursor-pointer items-center justify-between gap-2.5 rounded-lg border border-accent/35",
          "bg-surface-soft px-2.5 py-2 font-semibold text-fg hover:border-accent-strong",
          open && "border-accent-strong",
        )}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="text-[0.85rem] text-muted">{label}</span>
        <span className="max-w-[56%] truncate text-[0.85rem]">{summary}</span>
      </button>
      {open ? (
        <div
          className={cn(
            "absolute top-[calc(100%+6px)] left-0 z-30 w-full min-w-0 md:min-w-[260px]",
            "rounded-[10px] border border-accent/35 bg-panel/98 p-2 shadow-[0_10px_28px_rgb(0_0_0/0.52)] backdrop-blur-sm",
          )}
        >
          <input
            className="w-full rounded-lg border border-accent/35 bg-surface-soft px-2 py-[7px] text-[0.86rem] text-fg focus:border-accent-strong focus:outline-none"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${label.toLowerCase()}`}
          />
          <div className="mt-2 grid max-h-[220px] gap-[5px] overflow-auto">
            {filteredOptions.map((option) => {
              const isSelected = selectedValues.has(option);
              return (
                <button
                  type="button"
                  key={option}
                  aria-pressed={isSelected}
                  className={cn(
                    "grid w-full cursor-pointer grid-cols-[20px_minmax(0,1fr)] items-center gap-2 rounded-lg border",
                    "px-2 py-1.5 text-left font-semibold text-fg hover:border-accent-dim hover:bg-accent/20",
                    isSelected ? "border-accent-dim bg-accent/20" : "border-transparent bg-transparent",
                  )}
                  onClick={() => toggleValue(option)}
                >
                  <span aria-hidden="true">{isSelected ? "☑" : "☐"}</span>
                  <span>{option}</span>
                </button>
              );
            })}
            {filteredOptions.length === 0 ? (
              <div className="px-1 py-1.5 text-[0.84rem] text-muted">No matches</div>
            ) : null}
          </div>
          {selectedValues.size > 0 ? (
            <button
              type="button"
              className="mt-2 w-full cursor-pointer rounded-lg border border-accent/35 bg-transparent px-2 py-1.5 text-[0.82rem] font-semibold text-muted hover:bg-accent-strong hover:text-fg"
              onClick={() => onChange("")}
            >
              Clear
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
