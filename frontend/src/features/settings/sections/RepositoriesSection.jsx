import { useState } from "react";

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
      <SectionTitle className="mt-0">Repository Management</SectionTitle>
      <form className="mb-2.5 grid grid-cols-[1fr_auto] gap-2" onSubmit={onCreateRepository}>
        <Input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="New repository name"
          aria-label="New repository name"
        />
        <Button type="submit" size="lg">
          Create Repository
        </Button>
      </form>

      <Table headers={["Name", "Visibility"]}>
        {repositories.map((repo) => (
          <tr key={repo.id}>
            <td>{repo.name}</td>
            <td>{repo.is_public ? "Public" : "Private"}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}
