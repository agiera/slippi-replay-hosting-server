import { useState } from "react";

import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Table } from "../../../components/ui/Table";
import { createRepository } from "../../../lib/api/admin";
import { SectionTitle } from "../components/Headings";
import { sortByName } from "../listUtils";

export function RepositoriesSection({ repositories, setRepositories, run }) {
  const [newName, setNewName] = useState("");

  function onCreateRepository(event) {
    event.preventDefault();
    run(async () => {
      const created = await createRepository(newName.trim());
      setRepositories((prev) => sortByName([...prev, created]));
      setNewName("");
    });
  }

  return (
    <>
      <SectionTitle>Repository Management</SectionTitle>
      <form className="mt-4 flex gap-2" onSubmit={onCreateRepository}>
        <Input
          className="flex-1"
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="New repository name"
          aria-label="New repository name"
        />
        <Button type="submit">
          Create Repository
        </Button>
      </form>

      <Table className="mt-4" headers={["Name", "Visibility"]}>
        {repositories.map((repo) => (
          <tr key={repo.id}>
            <td>{repo.name}</td>
            <td>
              <Badge color={repo.is_public ? "green" : "gray"}>{repo.is_public ? "Public" : "Private"}</Badge>
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}
