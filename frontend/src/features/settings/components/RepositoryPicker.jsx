import { cn } from "../../../lib/cn";
import { toggleId } from "../listUtils";

// Pills for assigning repositories to a user; each click saves immediately via onChange.
export function RepositoryPicker({ repositories, selectedIds, onChange, disabled = false }) {
  if (!repositories.length) {
    return <p className="mt-0 text-muted">No repositories available.</p>;
  }

  return (
    <div
      className="flex min-h-[44px] flex-wrap gap-1.5 rounded-[10px] border border-accent/35 bg-accent/8 p-1.5"
      role="group"
      aria-label="Repository selector"
    >
      {repositories.map((repo) => {
        const selected = selectedIds.includes(repo.id);
        return (
          <button
            key={repo.id}
            type="button"
            className={cn(
              "cursor-pointer rounded-full border px-2.5 py-1.5 text-[0.82rem] leading-none font-semibold",
              "disabled:cursor-not-allowed disabled:opacity-60",
              selected
                ? "border-accent-strong bg-accent text-white"
                : "border-accent-dim bg-transparent text-muted enabled:hover:bg-accent/30 enabled:hover:text-fg",
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
