import { cn } from "../../../lib/cn";

const SIZES = {
  character: { chip: "size-8 p-1", icon: "pixelated size-6" },
  rank: { chip: "size-9 p-1", icon: "size-7" },
  costume: { chip: "size-7 p-1", icon: "pixelated size-5" },
};

// Toggleable icon button used by the character, rank and costume pickers.
export function IconChip({ size = "character", active, icon, fallback, label, onClick }) {
  const sizing = SIZES[size];
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "flex cursor-pointer items-center justify-center rounded-md transition",
        sizing.chip,
        active
          ? "bg-indigo-500/20 ring-1 ring-inset ring-indigo-400"
          : "opacity-60 hover:bg-white/10 hover:opacity-100",
      )}
    >
      {icon ? <img src={icon} alt="" className={cn("object-contain", sizing.icon)} /> : <span>{fallback}</span>}
    </button>
  );
}
