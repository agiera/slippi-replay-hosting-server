import { cn } from "../../lib/cn";

export function Card({ className, ...props }) {
  return (
    <section
      className={cn(
        "w-full rounded-[18px] border border-accent/35 bg-surface/94 p-7 shadow-[0_20px_40px_rgb(0_0_0/0.45)]",
        className,
      )}
      {...props}
    />
  );
}
