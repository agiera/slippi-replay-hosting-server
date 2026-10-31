import { cn } from "../../lib/cn";
import { ChevronDownIcon } from "./icons";
import { FIELD_CLASS } from "./Input";

const SIZES = {
  sm: "py-1 pr-8 pl-2.5",
  md: "py-1.5 pr-8 pl-3",
};

// Native select with a chevron. `className` sizes the wrapper (width, flex).
export function Select({ size = "md", className, ...props }) {
  return (
    <div className={cn("grid grid-cols-1", className)}>
      <select
        className={cn(FIELD_CLASS, SIZES[size], "col-start-1 row-start-1 appearance-none *:bg-gray-800")}
        {...props}
      />
      <ChevronDownIcon className="pointer-events-none col-start-1 row-start-1 mr-2 size-4 self-center justify-self-end text-gray-400" />
    </div>
  );
}
