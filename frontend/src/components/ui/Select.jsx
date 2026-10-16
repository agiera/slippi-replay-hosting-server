import { cn } from "../../lib/cn";

export function Select({ className, ...props }) {
  return (
    <select
      className={cn(
        "select-chevron w-full appearance-none rounded-[10px] border border-accent/35 bg-surface-soft",
        "py-2.5 pr-[34px] pl-3 text-[0.95rem] text-fg",
        "focus:border-accent-strong focus:ring-2 focus:ring-accent/24 focus:outline-none",
        "disabled:cursor-not-allowed disabled:opacity-65",
        className,
      )}
      {...props}
    />
  );
}
