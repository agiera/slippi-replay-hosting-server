import { useEffect, useMemo, useState } from "react";

import {
  createRepository,
  createMyApiToken,
  fetchMe,
  getStoredUser,
  listMyApiTokens,
  listRepositories,
  listUsers,
  revokeMyApiToken,
  updateUserRole,
  updateUserRepositories,
} from "../lib/api";

const ROLE_OPTIONS = ["user", "uploader", "superuser"];

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
  const [collectionName, setCollectionName] = useState("");
  const [newRepositoryName, setNewRepositoryName] = useState("");
  const [selectedRepositoryIds, setSelectedRepositoryIds] = useState([]);
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

      if (currentUser.role === "superuser") {
        const repositoryList = await listRepositories();
        setRepositories(repositoryList);
        const userList = await listUsers();
        setUsers(userList);
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
        collection_name: collectionName.trim(),
        repository_ids: selectedRepositoryIds,
      };
      const created = await createMyApiToken(payload);
      setNewTokenValue(created.token);
      setCollectionName("");
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

        <h2>API Tokens (Collections)</h2>
        {canCreateToken ? (
          <form className="settings-inline-form settings-token-form" onSubmit={onCreateToken}>
            <input
              value={collectionName}
              onChange={(e) => setCollectionName(e.target.value)}
              maxLength={64}
              placeholder="Unique collection name"
              required
            />
            <RepositoryPicker
              repositories={availableTokenRepositories}
              selectedIds={selectedRepositoryIds}
              onChange={setSelectedRepositoryIds}
            />
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
                  <td>{token.collection_name}</td>
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
        </section>
      )}
    </main>
  );
}
