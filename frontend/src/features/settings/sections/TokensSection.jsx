import { useEffect, useState } from "react";

import { Badge } from "../../../components/ui/Badge";
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
        <form className="mt-4 grid grid-cols-1 gap-2 md:flex" onSubmit={onCreateToken}>
          <Input
            className="md:flex-1"
            value={sourceName}
            onChange={(event) => setSourceName(event.target.value)}
            maxLength={64}
            placeholder="Unique source name"
            aria-label="Source name"
            required
          />
          <Select
            className="md:flex-1"
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
          <Button type="submit">
            Create Token
          </Button>
        </form>
      ) : (
        <Hint>You need uploader approval from a superuser to create upload tokens.</Hint>
      )}

      {newTokenValue ? (
        <div className="mt-4 rounded-md bg-indigo-500/10 p-4 ring-1 ring-inset ring-indigo-500/20">
          <p className="text-sm font-medium text-white">Copy this token now. It will not be shown again.</p>
          <code className="mt-2 block font-mono text-sm break-all text-indigo-300">{newTokenValue}</code>
        </div>
      ) : null}

      <Table className="mt-4" headers={["Name", "Repositories", "Prefix", "Created", "Status", "Action"]}>
        {tokens.length === 0 ? <EmptyRow colSpan={6}>No API tokens yet.</EmptyRow> : null}
        {tokens.map((token) => (
          <tr key={token.id}>
            <td>{token.source_name || token.collection_name}</td>
            <td>{(token.repositories || []).map((repo) => repo.name).join(", ") || "public"}</td>
            <td>{token.token_prefix}...</td>
            <td>{new Date(token.created_at).toLocaleString()}</td>
            <td>
              <Badge color={token.revoked_at ? "gray" : "green"}>{token.revoked_at ? "Revoked" : "Active"}</Badge>
            </td>
            <td>
              {!token.revoked_at ? (
                <Button variant="danger" size="sm" onClick={() => onRevokeToken(token.id)}>
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
