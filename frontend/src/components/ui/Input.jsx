import { cn } from "../../lib/cn";

// Shared with Select and MultiSelect so every field looks the same.
export const FIELD_CLASS = cn(
  "block w-full min-w-0 rounded-md bg-white/5 text-sm/6 text-white",
  "outline-1 -outline-offset-1 outline-white/10 placeholder:text-gray-500",
  "focus:outline-2 focus:-outline-offset-2 focus:outline-indigo-500",
  "disabled:cursor-not-allowed disabled:opacity-50",
);

const SIZES = {
  sm: "px-2.5 py-1",
  md: "px-3 py-1.5",
};

export function Input({ size = "md", className, ...props }) {
  return <input className={cn(FIELD_CLASS, SIZES[size], className)} {...props} />;
}
