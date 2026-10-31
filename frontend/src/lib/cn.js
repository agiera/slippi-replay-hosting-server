import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// Joins conditional class names and lets later Tailwind classes override earlier ones.
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
