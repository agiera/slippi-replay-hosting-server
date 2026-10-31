import { cn } from "../../../lib/cn";

// Switch for a series' public/private visibility, labelled with the current state.
export function VisibilityToggle({ active, onToggle, disabled = false }) {
  return (
    <div className={cn("flex items-center gap-3", disabled && "opacity-50")}>
      <button
        type="button"
        role="switch"
        aria-checked={active}
        aria-label="Public"
        onClick={onToggle}
        disabled={disabled}
        className={cn(
          "relative inline-flex w-11 shrink-0 cursor-pointer rounded-full p-0.5 ring-1 ring-inset transition-colors duration-200",
          "disabled:cursor-not-allowed",
          active ? "bg-indigo-500 ring-indigo-500" : "bg-white/5 ring-white/10",
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "size-5 rounded-full bg-white shadow-xs ring-1 ring-gray-900/5 transition-transform duration-200",
            active ? "translate-x-5" : "translate-x-0",
          )}
        />
      </button>
      <span className="text-sm text-gray-300">{active ? "Public" : "Private"}</span>
    </div>
  );
}
