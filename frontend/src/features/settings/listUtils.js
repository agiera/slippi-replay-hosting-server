// Small immutable helpers for the admin lists on the settings page.

export function sortByName(items) {
  return [...items].sort((a, b) => a.name.localeCompare(b.name));
}

export function replaceById(items, updated) {
  return items.map((item) => (item.id === updated.id ? updated : item));
}

// Adds `id` if missing, removes it if present.
export function toggleId(ids, id) {
  return ids.includes(id) ? ids.filter((existing) => existing !== id) : [...ids, id];
}

// Default repository for a new API token: the viewer's own first repository,
// else the first one they could pick. Returns "" when there is none.
export function defaultTokenRepositoryId(me, availableRepositories) {
  const fallback = me?.repositories?.[0] ?? availableRepositories[0];
  return fallback ? String(fallback.id) : "";
}
