import { cn } from "../../../lib/cn";

const SIZES = {
  character: { chip: "size-7 p-0.5", icon: "size-[22px] [image-rendering:pixelated]" },
  rank: { chip: "size-8 p-0.5", icon: "size-6" },
  costume: { chip: "size-6 p-px", icon: "size-5 [image-rendering:pixelated]" },
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
        "flex cursor-pointer items-center justify-center rounded-md border transition-[opacity,border-color,background-color] duration-[120ms]",
        sizing.chip,
        active
          ? "border-accent-strong bg-accent/32 opacity-100"
          : "border-transparent bg-transparent opacity-55 hover:border-accent-dim hover:bg-accent/18 hover:opacity-100",
      )}
    >
      {icon ? <img src={icon} alt="" className={cn("object-contain", sizing.icon)} /> : <span>{fallback}</span>}
    </button>
  );
}
