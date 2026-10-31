import { cn } from "../../lib/cn";

const VARIANTS = {
  primary: "bg-indigo-500 text-white shadow-xs hover:bg-indigo-400",
  secondary: "bg-white/10 text-white shadow-xs ring-1 ring-inset ring-white/5 hover:bg-white/20",
  ghost: "text-gray-300 hover:bg-white/5 hover:text-white",
  danger: "bg-red-500/10 text-red-400 ring-1 ring-inset ring-red-500/20 hover:bg-red-500/20",
};

const SIZES = {
  sm: "rounded-md px-2.5 py-1.5 text-sm",
  md: "rounded-md px-3 py-2 text-sm",
  lg: "rounded-md px-3.5 py-2.5 text-sm",
};

export function buttonClass({ variant = "primary", size = "md", className } = {}) {
  return cn(
    "inline-flex cursor-pointer items-center justify-center gap-x-1.5 font-semibold whitespace-nowrap no-underline",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500",
    "disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50",
    VARIANTS[variant],
    SIZES[size],
    className,
  );
}

export function Button({ variant, size, className, type = "button", ...props }) {
  return <button type={type} className={buttonClass({ variant, size, className })} {...props} />;
}

// Anchor styled as a button, for links (deep links, external viewers).
export function ButtonLink({ variant, size, className, ...props }) {
  return <a className={buttonClass({ variant, size, className })} {...props} />;
}
