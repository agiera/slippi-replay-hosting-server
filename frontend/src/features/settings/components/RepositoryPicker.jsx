import { cn } from "../../../lib/cn";
import { toggleId } from "../listUtils";

// Toggle buttons for assigning repositories to a user; each click saves immediately via onChange.
export function RepositoryPicker({ repositories, selectedIds, onChange, disabled = false }) {
  if (!repositories.length) {
    return <p className="text-sm text-gray-400">No repositories available.</p>;
  }

  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Repository selector">
      {repositories.map((repo) => {
        const selected = selectedIds.includes(repo.id);
        return (
          <button
            key={repo.id}
            type="button"
            className={cn(
              "cursor-pointer rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset",
              "disabled:cursor-not-allowed disabled:opacity-50",
              selected
                ? "bg-indigo-500 text-white ring-indigo-500 enabled:hover:bg-indigo-400"
                : "bg-white/5 text-gray-300 ring-white/10 enabled:hover:bg-white/10 enabled:hover:text-white",
            )}
            onClick={() => onChange(toggleId(selectedIds, repo.id))}
            disabled={disabled}
            aria-pressed={selected}
            title={repo.is_public ? `${repo.name} (public)` : repo.name}
          >
            {repo.name}
          </button>
        );
      })}
    </div>
  );
}
