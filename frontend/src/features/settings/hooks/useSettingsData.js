import { useCallback, useEffect, useState } from "react";

import {
  listMyApiTokens,
  listRepositories,
  listSources,
  listTournaments,
  listUsers,
} from "../../../lib/api/admin";
import { fetchMe } from "../../../lib/api/auth";
import { getStoredUser } from "../../../lib/api/session";
import { replaceById } from "../listUtils";

/**
 * Loads everything the settings page shows. Superusers also get every
 * repository, user, source and tournament series; other users only see the
 * repositories they belong to.
 *
 * `run(action)` wraps a section's API call: it clears the shared error first
 * and reports a failure in it, so sections don't each need try/catch.
 */
export function useSettingsData() {
  const [me, setMe] = useState(getStoredUser());
  const [tokens, setTokens] = useState([]);
  const [repositories, setRepositories] = useState([]);
  const [users, setUsers] = useState([]);
  const [sources, setSources] = useState([]);
  const [tournaments, setTournaments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const currentUser = await fetchMe();
        setMe(currentUser);
        setTokens(await listMyApiTokens());

        if (currentUser.role === "superuser") {
          setRepositories(await listRepositories());
          setUsers(await listUsers());
          setSources(await listSources());
          setTournaments(await listTournaments());
        } else {
          setRepositories(currentUser.repositories || []);
        }
      } catch (err) {
        setError(err.message || "Failed to load settings");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const run = useCallback(async (action) => {
    setError("");
    try {
      return await action();
    } catch (err) {
      setError(err.message);
      return undefined;
    }
  }, []);

  // A user's role or repositories changed: update the list, and `me` if it's the viewer.
  const applyUserUpdate = useCallback((updated) => {
    setUsers((prev) => replaceById(prev, updated));
    setMe((prev) => (prev?.id === updated.id ? updated : prev));
  }, []);

  return {
    loading,
    error,
    run,
    me,
    isSuperuser: me?.role === "superuser",
    canCreateToken: ["uploader", "superuser"].includes(me?.role),
    tokens,
    setTokens,
    repositories,
    setRepositories,
    users,
    applyUserUpdate,
    sources,
    tournaments,
    setTournaments,
  };
}
