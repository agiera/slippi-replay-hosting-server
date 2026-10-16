import { cn } from "../../lib/cn";

const COLORS = {
  gray: "bg-gray-400/10 text-gray-400 ring-gray-400/20",
  indigo: "bg-indigo-400/10 text-indigo-400 ring-indigo-400/30",
  green: "bg-green-500/10 text-green-400 ring-green-500/20",
  yellow: "bg-yellow-400/10 text-yellow-500 ring-yellow-400/20",
  red: "bg-red-400/10 text-red-400 ring-red-400/20",
};

const DOT_COLORS = {
  gray: "fill-gray-400",
  indigo: "fill-indigo-400",
  green: "fill-green-400",
  yellow: "fill-yellow-500",
  red: "fill-red-400",
};

// Small status label. `dot` adds a coloured dot before the text.
export function Badge({ color = "gray", dot = false, className, children }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-x-1.5 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset",
        COLORS[color],
        className,
      )}
    >
      {dot ? (
        <svg viewBox="0 0 6 6" aria-hidden="true" className={cn("size-1.5", DOT_COLORS[color])}>
          <circle r={3} cx={3} cy={3} />
        </svg>
      ) : null}
      {children}
    </span>
  );
}
