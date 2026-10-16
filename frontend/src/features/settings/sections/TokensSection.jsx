import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { EmptyRow, Table } from "../../../components/ui/Table";
import { createMyApiToken, listMyApiTokens, revokeMyApiToken } from "../../../lib/api/admin";
import { Hint, SectionTitle } from "../components/Headings";
import { defaultTokenRepositoryId } from "../listUtils";

// The viewer's upload tokens: one per source (setup), scoped to a repository.
export function TokensSection({ me, isSuperuser, canCreateToken, repositories, tokens, setTokens, run }) {
  const [sourceName, setSourceName] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [newTokenValue, setNewTokenValue] = useState("");

  const availableRepositories = isSuperuser ? repositories : me?.repositories || [];

  useEffect(() => {
    if (!repositoryId) {
      setRepositoryId(defaultTokenRepositoryId(me, availableRepositories));
    }
  }, [me, availableRepositories, repositoryId]);

  async function onCreateToken(event) {
    event.preventDefault();
    setNewTokenValue("");
    await run(async () => {
      const created = await createMyApiToken({
        source_name: sourceName.trim(),
        repository_ids: repositoryId ? [Number(repositoryId)] : [],
      });
      setNewTokenValue(created.token);
      setSourceName("");
      setTokens(await listMyApiTokens());
    });
  }

  function onRevokeToken(id) {
    run(async () => {
      await revokeMyApiToken(id);
      const revokedAt = new Date().toISOString();
      setTokens((prev) => prev.map((token) => (token.id === id ? { ...token, revoked_at: revokedAt } : token)));
    });
  }

  return (
    <>
      <SectionTitle>API Tokens (Sources)</SectionTitle>
      {canCreateToken ? (
        <form className="mb-2.5 grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_auto]" onSubmit={onCreateToken}>
          <Input
            value={sourceName}
            onChange={(event) => setSourceName(event.target.value)}
            maxLength={64}
            placeholder="Unique source name"
            aria-label="Source name"
            required
          />
          <Select
            value={repositoryId}
            onChange={(event) => setRepositoryId(event.target.value)}
            aria-label="Repository"
            required
          >
            <option value="" disabled>
              Select repository
            </option>
            {availableRepositories.map((repo) => (
              <option key={repo.id} value={String(repo.id)}>
                {repo.name}
              </option>
            ))}
          </Select>
          <Button type="submit" size="lg">
            Create Token
          </Button>
        </form>
      ) : (
        <Hint>You need uploader approval from a superuser to create upload tokens.</Hint>
      )}

      {newTokenValue ? (
        <div className="mb-3 rounded-[10px] border border-accent/35 bg-accent/14 p-2.5">
          <p className="mt-0 mb-2">Copy this token now. It will not be shown again.</p>
          <code className="block text-[0.86rem] [overflow-wrap:anywhere]">{newTokenValue}</code>
        </div>
      ) : null}

      <Table headers={["Name", "Repositories", "Prefix", "Created", "Status", "Action"]}>
        {tokens.length === 0 ? <EmptyRow colSpan={6}>No API tokens yet.</EmptyRow> : null}
        {tokens.map((token) => (
          <tr key={token.id}>
            <td>{token.source_name || token.collection_name}</td>
            <td>{(token.repositories || []).map((repo) => repo.name).join(", ") || "public"}</td>
            <td>{token.token_prefix}...</td>
            <td>{new Date(token.created_at).toLocaleString()}</td>
            <td>{token.revoked_at ? "Revoked" : "Active"}</td>
            <td>
              {!token.revoked_at ? (
                <Button variant="ghost" size="sm" onClick={() => onRevokeToken(token.id)}>
                  Revoke
                </Button>
              ) : null}
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}
