import { cn } from "../../../lib/cn";

export function SectionTitle({ className, ...props }) {
  return <h2 className={cn("mt-6 mb-3 text-2xl font-bold", className)} {...props} />;
}

export function SubsectionTitle({ title, description }) {
  return (
    <>
      <h3 className="mt-3.5 mb-1 text-[0.98rem] font-bold tracking-[0.02em] text-subtle">{title}</h3>
      {description ? <p className="mt-0 mb-2 text-[0.86rem] text-muted">{description}</p> : null}
    </>
  );
}

export function Hint({ className, ...props }) {
  return <p className={cn("mt-0 mb-4 text-muted", className)} {...props} />;
}
