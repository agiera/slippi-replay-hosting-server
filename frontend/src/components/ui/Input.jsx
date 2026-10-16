import { cn } from "../../lib/cn";

const SIZES = {
  sm: "rounded-lg px-2.5 py-1.5 text-[0.88rem]",
  md: "rounded-[10px] px-3 py-2.5 text-base",
};

export function Input({ size = "md", className, ...props }) {
  return (
    <input
      className={cn(
        "w-full min-w-0 border border-accent/35 bg-surface-soft text-fg placeholder:text-muted/80",
        "focus:border-accent-strong focus:outline-none",
        SIZES[size],
        className,
      )}
      {...props}
    />
  );
}
