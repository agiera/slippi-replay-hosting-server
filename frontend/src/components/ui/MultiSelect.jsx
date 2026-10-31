import { useCallback, useRef, useState } from "react";

import { cn } from "../../lib/cn";
import { CheckIcon, ChevronDownIcon } from "./icons";
import { FIELD_CLASS } from "./Input";
import { useDismiss } from "./useDismiss";

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
  const triggerRef = useRef(null);

  const selectedValues = new Set(splitValues(selected));
  const normalizedQuery = query.toLowerCase().trim();
  const filteredOptions = options.filter((option) => option.toLowerCase().includes(normalizedQuery));

  const close = useCallback((reason) => {
    setOpen(false);
    if (reason === "escape") {
      triggerRef.current?.focus();
    }
  }, []);
  useDismiss(rootRef, open, close);

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
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        className={cn(
          "flex w-full cursor-pointer items-center gap-2 rounded-md bg-white/5 py-1.5 pr-2 pl-3 text-left text-sm/6",
          "outline-1 -outline-offset-1 outline-white/10 hover:bg-white/10",
          "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-indigo-500",
        )}
        onClick={() => setOpen((prev) => !prev)}
      >
        <span className="text-gray-400">{label}</span>
        <span className="ml-auto truncate font-medium text-white">{summary}</span>
        <ChevronDownIcon className="size-4 shrink-0 text-gray-400" />
      </button>
      {open ? (
        <div className="absolute inset-x-0 z-30 mt-1 rounded-md bg-gray-800 p-2 shadow-lg ring-1 ring-white/10">
          <input
            className={cn(FIELD_CLASS, "px-2.5 py-1")}
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${label.toLowerCase()}`}
            aria-label={`Search ${label.toLowerCase()}`}
          />
          <div className="mt-2 max-h-60 overflow-auto">
            {filteredOptions.map((option) => {
              const isSelected = selectedValues.has(option);
              return (
                <button
                  type="button"
                  key={option}
                  aria-pressed={isSelected}
                  className={cn(
                    "flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-white",
                    "hover:bg-indigo-500",
                  )}
                  onClick={() => toggleValue(option)}
                >
                  <span className={cn("truncate", isSelected && "font-semibold")}>{option}</span>
                  {isSelected ? <CheckIcon className="ml-auto size-4 shrink-0 text-indigo-300" /> : null}
                </button>
              );
            })}
            {filteredOptions.length === 0 ? <p className="px-2 py-1.5 text-sm text-gray-400">No matches</p> : null}
          </div>
          {selectedValues.size > 0 ? (
            <button
              type="button"
              className="mt-2 w-full cursor-pointer rounded-md px-2 py-1.5 text-sm font-semibold text-gray-300 hover:bg-white/5 hover:text-white"
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
