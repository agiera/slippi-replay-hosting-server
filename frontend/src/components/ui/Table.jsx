import { cn } from "../../lib/cn";

// Scrollable table: white header text, muted cells, the first column emphasised.
export function Table({ headers, children, className }) {
  return (
    <div className={cn("-mx-6 overflow-x-auto px-6", className)}>
      <table className="min-w-full divide-y divide-white/15">
        <thead>
          <tr>
            {headers.map((header, idx) => (
              <th
                key={header}
                scope="col"
                className={cn(
                  "px-3 py-3.5 text-left text-sm font-semibold whitespace-nowrap text-white",
                  idx === 0 && "pl-0",
                )}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody
          className={cn(
            "divide-y divide-white/10",
            "[&_td]:px-3 [&_td]:py-3 [&_td]:align-middle [&_td]:text-sm [&_td]:text-gray-400",
            "[&_td:first-child]:pl-0 [&_td:first-child]:font-medium [&_td:first-child]:text-white",
          )}
        >
          {children}
        </tbody>
      </table>
    </div>
  );
}

export function EmptyRow({ colSpan, children }) {
  return (
    <tr>
      <td colSpan={colSpan} className="text-gray-400">
        {children}
      </td>
    </tr>
  );
}
