import { cn } from "../../../lib/cn";

export function SectionTitle({ className, ...props }) {
  return <h2 className={cn("text-base/7 font-semibold text-white", className)} {...props} />;
}

export function SubsectionTitle({ title, description }) {
  return (
    <div className="mt-8 mb-3">
      <h3 className="text-sm/6 font-semibold text-white">{title}</h3>
      {description ? <p className="text-sm/6 text-gray-400">{description}</p> : null}
    </div>
  );
}

export function Hint({ className, ...props }) {
  return <p className={cn("mt-1 mb-4 text-sm/6 text-gray-400", className)} {...props} />;
}
