import { cn } from "../../lib/cn";

export function Card({ className, ...props }) {
  return <section className={cn("w-full rounded-lg bg-gray-900 p-6 ring-1 ring-white/10", className)} {...props} />;
}
