import { Select } from "../../../components/ui/Select";
import { Table } from "../../../components/ui/Table";
import { updateUserRepositories, updateUserRole } from "../../../lib/api/admin";
import { RepositoryPicker } from "../components/RepositoryPicker";
import { SectionTitle } from "../components/Headings";
import { ROLE_OPTIONS } from "../constants";

// Role and repository access for every user. Changes save immediately.
export function UsersSection({ me, users, repositories, applyUserUpdate, run }) {
  function onRoleChange(userId, role) {
    run(async () => applyUserUpdate(await updateUserRole(userId, role)));
  }

  function onRepositoriesChange(userId, repositoryIds) {
    run(async () => applyUserUpdate(await updateUserRepositories(userId, repositoryIds)));
  }

  return (
    <>
      <SectionTitle>User Role Management</SectionTitle>
      <Table headers={["Username", "Email", "Role", "Repositories"]}>
        {users.map((user) => (
          <tr key={user.id}>
            <td>{user.username}</td>
            <td>{user.email}</td>
            <td>
              <Select
                size="sm"
                className="w-32"
                value={user.role}
                onChange={(event) => onRoleChange(user.id, event.target.value)}
                disabled={user.id === me.id}
                aria-label={`Role for ${user.username}`}
                title={user.id === me.id ? "You can't change your own role" : undefined}
              >
                {ROLE_OPTIONS.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </Select>
            </td>
            <td>
              <RepositoryPicker
                repositories={repositories}
                selectedIds={(user.repositories || []).map((repo) => repo.id)}
                onChange={(nextIds) => onRepositoriesChange(user.id, nextIds)}
              />
            </td>
          </tr>
        ))}
      </Table>
    </>
  );
}
