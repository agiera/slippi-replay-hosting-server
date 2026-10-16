import { cn } from "../../lib/cn";

// Bordered, scrollable table with a tinted header row.
export function Table({ headers, children, className }) {
  return (
    <div className={cn("overflow-auto rounded-xl border border-accent/35", className)}>
      <table
        className={cn(
          "w-full border-collapse bg-surface",
          "[&_td]:border-b [&_td]:border-accent/22 [&_td]:px-3 [&_td]:py-2.5 [&_td]:text-left [&_td]:text-[0.92rem]",
          "[&_th]:border-b [&_th]:border-accent/22 [&_th]:bg-surface-soft [&_th]:px-3 [&_th]:py-2.5",
          "[&_th]:text-left [&_th]:text-[0.92rem] [&_th]:font-bold [&_th]:text-accent-strong",
        )}
      >
        <thead>
          <tr>
            {headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function EmptyRow({ colSpan, children }) {
  return (
    <tr>
      <td colSpan={colSpan} className="text-muted">
        {children}
      </td>
    </tr>
  );
}
