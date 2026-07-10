import { useEffect, useMemo, useState } from "react";

import {
  createTournament,
  createRepository,
  createMyApiToken,
  fetchMe,
  getTournamentSourceIds,
  getStoredUser,
  listSources,
  listTournaments,
  listMyApiTokens,
  listRepositories,
  listUsers,
  revokeMyApiToken,
  updateTournament,
  updateTournamentSources,
  updateUserRole,
  updateUserRepositories,
} from "../lib/api";

const ROLE_OPTIONS = ["user", "uploader", "superuser"];
const TOURNAMENT_PROVIDERS = [
  { value: "", label: "No provider" },
  { value: "startgg", label: "start.gg" },
  { value: "parrygg", label: "parry.gg" },
];

function ToggleChip({ active, onToggle, disabled = false, activeLabel = "Public", inactiveLabel = "Private" }) {
  return (
    <button
      type="button"
      className={`chip-toggle ${active ? "active" : ""}`}
      onClick={onToggle}
      disabled={disabled}
      aria-pressed={active}
      title={active ? activeLabel : inactiveLabel}
    >
      <span className="chip-toggle-label">Visibility</span>
      <span className="chip-toggle-value">{active ? activeLabel : inactiveLabel}</span>
    </button>
  );
}

function RepositoryPicker({ repositories, selectedIds, onChange, disabled = false }) {
  const selectedSet = new Set(selectedIds);

  function toggleRepository(id) {
    if (disabled) {
      return;
    }
    if (selectedSet.has(id)) {
      onChange(selectedIds.filter((existingId) => existingId !== id));
      return;
    }
    onChange([...selectedIds, id]);
  }

  if (!repositories.length) {
    return <p className="subtitle">No repositories available.</p>;
  }

  return (
    <div className="repo-picker" role="group" aria-label="Repository selector">
      {repositories.map((repo) => {
        const selected = selectedSet.has(repo.id);
        return (
          <button
            key={repo.id}
            type="button"
            className={`repo-pill ${selected ? "selected" : ""}`}
            onClick={() => toggleRepository(repo.id)}
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

export default function Settings() {
  const [me, setMe] = useState(getStoredUser());
  const [tokens, setTokens] = useState([]);
  const [users, setUsers] = useState([]);
  const [repositories, setRepositories] = useState([]);
  const [sourceName, setSourceName] = useState("");
  const [sources, setSources] = useState([]);
  const [tournaments, setTournaments] = useState([]);
  const [newTournamentName, setNewTournamentName] = useState("");
  const [newTournamentProvider, setNewTournamentProvider] = useState("");
  const [newTournamentSlug, setNewTournamentSlug] = useState("");
  const [newTournamentIsPublic, setNewTournamentIsPublic] = useState(false);
  const [selectedTournamentId, setSelectedTournamentId] = useState("");
  const [selectedTournamentSourceIds, setSelectedTournamentSourceIds] = useState([]);
  const [selectedTournamentProvider, setSelectedTournamentProvider] = useState("");
  const [selectedTournamentSlug, setSelectedTournamentSlug] = useState("");
  const [selectedTournamentIsPublic, setSelectedTournamentIsPublic] = useState(false);
  const [newRepositoryName, setNewRepositoryName] = useState("");
  const [selectedRepositoryIds, setSelectedRepositoryIds] = useState([]);
  const [selectedTokenRepositoryId, setSelectedTokenRepositoryId] = useState("");
  const [newTokenValue, setNewTokenValue] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const canCreateToken = useMemo(() => {
    return me && ["uploader", "superuser"].includes(me.role);
  }, [me]);

  const isSuperuser = me?.role === "superuser";

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const currentUser = await fetchMe();
      setMe(currentUser);
      const tokenList = await listMyApiTokens();
      setTokens(tokenList);
      setSelectedRepositoryIds((currentUser.repositories || []).map((repo) => repo.id));
      if (!selectedTokenRepositoryId && (currentUser.repositories || []).length > 0) {
        setSelectedTokenRepositoryId(String(currentUser.repositories[0].id));
      }

      if (currentUser.role === "superuser") {
        const repositoryList = await listRepositories();
        setRepositories(repositoryList);
        const userList = await listUsers();
        setUsers(userList);
        const sourceList = await listSources();
        setSources(sourceList);
        const tournamentList = await listTournaments();
        setTournaments(tournamentList);
      } else {
        setRepositories(currentUser.repositories || []);
      }
    } catch (err) {
      setError(err.message || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  async function onCreateToken(e) {
    e.preventDefault();
    setError("");
    setNewTokenValue("");
    try {
      const payload = {
        source_name: sourceName.trim(),
        repository_ids: selectedTokenRepositoryId ? [Number(selectedTokenRepositoryId)] : [],
      };
      const created = await createMyApiToken(payload);
      setNewTokenValue(created.token);
      setSourceName("");
      const tokenList = await listMyApiTokens();
      setTokens(tokenList);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onCreateRepository(e) {
    e.preventDefault();
    setError("");
    try {
      const created = await createRepository(newRepositoryName.trim());
      setRepositories((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setNewRepositoryName("");
    } catch (err) {
      setError(err.message);
    }
  }

  async function onUserRepositoriesChange(userId, repositoryIds) {
    setError("");
    try {
      const updated = await updateUserRepositories(userId, repositoryIds);
      setUsers((prev) => prev.map((user) => (user.id === updated.id ? updated : user)));
      if (updated.id === me.id) {
        setMe(updated);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  const availableTokenRepositories = isSuperuser ? repositories : me?.repositories || [];

  useEffect(() => {
    if (selectedTokenRepositoryId) {
      return;
    }
    if (availableTokenRepositories.length > 0) {
      setSelectedTokenRepositoryId(String(availableTokenRepositories[0].id));
    }
  }, [availableTokenRepositories, selectedTokenRepositoryId]);

  async function onRevokeToken(id) {
    setError("");
    try {
      await revokeMyApiToken(id);
      setTokens((prev) =>
        prev.map((token) => (token.id === id ? { ...token, revoked_at: new Date().toISOString() } : token))
      );
    } catch (err) {
      setError(err.message);
    }
  }

  async function onRoleChange(userId, role) {
    setError("");
    try {
      const updated = await updateUserRole(userId, role);
      setUsers((prev) => prev.map((user) => (user.id === updated.id ? updated : user)));
      if (updated.id === me.id) {
        setMe(updated);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function onCreateTournament(e) {
    e.preventDefault();
    setError("");
    try {
      const created = await createTournament({
        name: newTournamentName.trim(),
        is_public: newTournamentIsPublic,
        provider: newTournamentProvider || null,
        slug: newTournamentSlug.trim() || null,
      });
      setTournaments((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      setNewTournamentName("");
      setNewTournamentProvider("");
      setNewTournamentSlug("");
      setNewTournamentIsPublic(false);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onSelectTournament(tournamentId) {
    setSelectedTournamentId(tournamentId);
    if (!tournamentId) {
      setSelectedTournamentSourceIds([]);
      setSelectedTournamentProvider("");
      setSelectedTournamentSlug("");
      setSelectedTournamentIsPublic(false);
      return;
    }

    const selectedTournament = tournaments.find((t) => String(t.id) === String(tournamentId));
    setSelectedTournamentProvider(selectedTournament?.provider || "");
    setSelectedTournamentSlug(selectedTournament?.slug || "");
    setSelectedTournamentIsPublic(Boolean(selectedTournament?.is_public));

    setError("");
    try {
      const ids = await getTournamentSourceIds(tournamentId);
      setSelectedTournamentSourceIds(ids);
    } catch (err) {
      setError(err.message);
    }
  }

  async function onSaveTournamentMetadata() {
    if (!selectedTournamentId) {
      return;
    }
    setError("");
    try {
      const updated = await updateTournament(selectedTournamentId, {
        is_public: selectedTournamentIsPublic,
        provider: selectedTournamentProvider || null,
        slug: selectedTournamentSlug.trim() || null,
      });
      setTournaments((prev) =>
        prev
          .map((tournament) => (tournament.id === updated.id ? updated : tournament))
          .sort((a, b) => a.name.localeCompare(b.name))
      );
      setSelectedTournamentProvider(updated.provider || "");
      setSelectedTournamentSlug(updated.slug || "");
      setSelectedTournamentIsPublic(Boolean(updated.is_public));
    } catch (err) {
      setError(err.message);
    }
  }

  const selectedTournament = useMemo(
    () => tournaments.find((t) => String(t.id) === String(selectedTournamentId)) || null,
    [selectedTournamentId, tournaments]
  );

  async function onSaveTournamentSources() {
    if (!selectedTournamentId) {
      return;
    }
    setError("");
    try {
      await updateTournamentSources(selectedTournamentId, selectedTournamentSourceIds);
    } catch (err) {
      setError(err.message);
    }
  }

  function toggleTournamentSource(sourceId) {
    if (selectedTournamentSourceIds.includes(sourceId)) {
      setSelectedTournamentSourceIds((prev) => prev.filter((id) => id !== sourceId));
      return;
    }
    setSelectedTournamentSourceIds((prev) => [...prev, sourceId]);
  }

  if (loading) {
    return (
      <main className="settings-layout">
        <section className="settings-card">
          <p>Loading settings...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="settings-layout">
      <section className="settings-card">
        <h1>User Settings</h1>
        {me && (
          <p className="subtitle">
            Signed in as <strong>{me.username}</strong> ({me.role})
          </p>
        )}
        {error && <p className="error">{error}</p>}

        <h2>API Tokens (Sources)</h2>
        {canCreateToken ? (
          <form className="settings-inline-form settings-token-form" onSubmit={onCreateToken}>
            <input
              value={sourceName}
              onChange={(e) => setSourceName(e.target.value)}
              maxLength={64}
              placeholder="Unique source name"
              required
            />
            <select
              className="settings-select"
              value={selectedTokenRepositoryId}
              onChange={(e) => setSelectedTokenRepositoryId(e.target.value)}
              required
            >
              <option value="" disabled>Select repository</option>
              {availableTokenRepositories.map((repo) => (
                <option key={repo.id} value={String(repo.id)}>
                  {repo.name}
                </option>
              ))}
            </select>
            <button type="submit">Create Token</button>
          </form>
        ) : (
          <p className="subtitle">You need uploader approval from a superuser to create upload tokens.</p>
        )}

        {newTokenValue && (
          <div className="token-plain-box">
            <p>Copy this token now. It will not be shown again.</p>
            <code>{newTokenValue}</code>
          </div>
        )}

        <div className="settings-table-wrap">
          <table className="settings-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Repositories</th>
                <th>Prefix</th>
                <th>Created</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {tokens.length === 0 && (
                <tr>
                  <td colSpan={6}>No API tokens yet.</td>
                </tr>
              )}
              {tokens.map((token) => (
                <tr key={token.id}>
                  <td>{token.source_name || token.collection_name}</td>
                  <td>{(token.repositories || []).map((repo) => repo.name).join(", ") || "public"}</td>
                  <td>{token.token_prefix}...</td>
                  <td>{new Date(token.created_at).toLocaleString()}</td>
                  <td>{token.revoked_at ? "Revoked" : "Active"}</td>
                  <td>
                    {!token.revoked_at && (
                      <button type="button" className="ghost" onClick={() => onRevokeToken(token.id)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {isSuperuser && (
        <section className="settings-card">
          <h2>Repository Management</h2>
          <form className="settings-inline-form" onSubmit={onCreateRepository}>
            <input
              value={newRepositoryName}
              onChange={(e) => setNewRepositoryName(e.target.value)}
              placeholder="New repository name"
            />
            <button type="submit">Create Repository</button>
          </form>

          <div className="settings-table-wrap">
            <table className="settings-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Visibility</th>
                </tr>
              </thead>
              <tbody>
                {repositories.map((repo) => (
                  <tr key={repo.id}>
                    <td>{repo.name}</td>
                    <td>{repo.is_public ? "Public" : "Private"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>User Role Management</h2>
          <div className="settings-table-wrap">
            <table className="settings-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Repositories</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>{user.email}</td>
                    <td>
                      <select
                        value={user.role}
                        onChange={(e) => onRoleChange(user.id, e.target.value)}
                        disabled={user.id === me.id}
                      >
                        {ROLE_OPTIONS.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <RepositoryPicker
                        repositories={repositories}
                        selectedIds={(user.repositories || []).map((repo) => repo.id)}
                        onChange={(nextIds) => onUserRepositoriesChange(user.id, nextIds)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Tournament Series</h2>
          <h3 className="settings-subheader">New Tournament Series</h3>
          <p className="subtitle settings-subtitle">Create a new series, optionally attach a provider slug, and set visibility.</p>
          <form className="settings-inline-form settings-inline-form-wide" onSubmit={onCreateTournament}>
            <input
              value={newTournamentName}
              onChange={(e) => setNewTournamentName(e.target.value)}
              placeholder="New tournament series name"
            />
            <select
              className="settings-select"
              value={newTournamentProvider}
              onChange={(e) => setNewTournamentProvider(e.target.value)}
            >
              {TOURNAMENT_PROVIDERS.map((provider) => (
                <option key={provider.value || "none"} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </select>
            <input
              value={newTournamentSlug}
              onChange={(e) => setNewTournamentSlug(e.target.value)}
              placeholder="Tournament slug (optional)"
            />
            <ToggleChip
              active={newTournamentIsPublic}
              onToggle={() => setNewTournamentIsPublic((prev) => !prev)}
            />
            <button type="submit">Create Tournament</button>
          </form>

          <h3 className="settings-subheader">Save Existing Tournament Series</h3>
          <p className="subtitle settings-subtitle">Select an existing series to update source assignments and metadata.</p>
          <div className="settings-inline-form">
            <select
              className="settings-select"
              value={selectedTournamentId}
              onChange={(e) => onSelectTournament(e.target.value)}
            >
              <option value="">Select tournament</option>
              {tournaments.map((tournament) => (
                <option key={tournament.id} value={tournament.id}>
                  {tournament.name}
                </option>
              ))}
            </select>
            <button type="button" onClick={onSaveTournamentSources} disabled={!selectedTournamentId}>
              Save Sources
            </button>
          </div>

          <div className="settings-inline-form settings-inline-form-wide">
            <select
              className="settings-select"
              value={selectedTournamentProvider}
              onChange={(e) => setSelectedTournamentProvider(e.target.value)}
              disabled={!selectedTournamentId}
            >
              {TOURNAMENT_PROVIDERS.map((provider) => (
                <option key={`selected-${provider.value || "none"}`} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </select>
            <input
              value={selectedTournamentSlug}
              onChange={(e) => setSelectedTournamentSlug(e.target.value)}
              placeholder="Tournament slug"
              disabled={!selectedTournamentId}
            />
            <ToggleChip
              active={selectedTournamentIsPublic}
              onToggle={() => setSelectedTournamentIsPublic((prev) => !prev)}
              disabled={!selectedTournamentId}
            />
            <button type="button" onClick={onSaveTournamentMetadata} disabled={!selectedTournamentId}>
              Save Tournament Metadata
            </button>
          </div>

          {selectedTournament && (
            <p className="subtitle">
              Current resolved tournament name: {selectedTournament.current_tournament_name || "not resolved"}
            </p>
          )}

          <div className="settings-table-wrap">
            <table className="settings-table">
              <thead>
                <tr>
                  <th>Use</th>
                  <th>Source</th>
                  <th>Owner</th>
                  <th>Token Prefix</th>
                </tr>
              </thead>
              <tbody>
                {sources.length === 0 && (
                  <tr>
                    <td colSpan={4}>No sources found.</td>
                  </tr>
                )}
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedTournamentSourceIds.includes(source.id)}
                        onChange={() => toggleTournamentSource(source.id)}
                        disabled={!selectedTournamentId}
                      />
                    </td>
                    <td>{source.source_name}</td>
                    <td>{source.username}</td>
                    <td>{source.token_prefix}...</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
