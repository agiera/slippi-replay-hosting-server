import { cn } from "../../lib/cn";

const VARIANTS = {
  primary: "border-0 bg-accent text-fg hover:bg-accent-strong",
  secondary: "border border-accent/35 bg-transparent text-muted hover:bg-accent-strong hover:text-fg",
  ghost: "border border-accent bg-transparent text-accent-strong hover:bg-accent/20 hover:text-fg",
};

const SIZES = {
  sm: "rounded-lg px-2.5 py-1.5 text-[0.82rem]",
  md: "rounded-lg px-2.5 py-2 text-base",
};

export function buttonClass({ variant = "primary", size = "md", className } = {}) {
  return cn(
    "inline-flex cursor-pointer items-center justify-center font-semibold no-underline",
    "disabled:cursor-not-allowed disabled:opacity-55 aria-disabled:cursor-not-allowed aria-disabled:opacity-55",
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
