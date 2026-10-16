import { cn } from "../../../lib/cn";

// Pill switch for a series' public/private visibility.
export function VisibilityToggle({ active, onToggle, disabled = false }) {
  const label = active ? "Public" : "Private";
  return (
    <button
      type="button"
      className={cn(
        "inline-flex min-w-[156px] cursor-pointer items-center justify-between gap-2.5 rounded-full border",
        "px-3 py-2 leading-none font-semibold",
        "disabled:cursor-not-allowed disabled:opacity-55",
        active
          ? "border-accent-strong bg-accent/34 text-fg"
          : "border-accent/35 bg-accent/12 text-muted enabled:hover:border-accent-strong",
      )}
      onClick={onToggle}
      disabled={disabled}
      aria-pressed={active}
      title={label}
    >
      <span className="text-[0.78rem] tracking-[0.03em] uppercase">Visibility</span>
      <span className="text-[0.88rem] font-bold">{label}</span>
    </button>
  );
}
