import { cn } from "../../lib/cn";

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "w-full rounded-[10px] border border-accent/35 bg-surface-soft px-3 py-2.5 text-base text-fg",
        "focus:border-accent-strong focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}
