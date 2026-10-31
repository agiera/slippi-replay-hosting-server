import { Card } from "../components/ui/Card";
import { useSettingsData } from "../features/settings/hooks/useSettingsData";
import { RepositoriesSection } from "../features/settings/sections/RepositoriesSection";
import { TokensSection } from "../features/settings/sections/TokensSection";
import { TournamentsSection } from "../features/settings/sections/TournamentsSection";
import { UsersSection } from "../features/settings/sections/UsersSection";

function SettingsLayout({ children }) {
  return <main className="mx-auto max-w-5xl space-y-6 px-4 py-10 sm:px-6 lg:px-8">{children}</main>;
}

export default function Settings() {
  const settings = useSettingsData();
  const { me, run } = settings;

  if (settings.loading) {
    return (
      <SettingsLayout>
        <p className="text-sm text-gray-400">Loading settings...</p>
      </SettingsLayout>
    );
  }

  return (
    <SettingsLayout>
      <header>
        <h1 className="text-2xl/9 font-bold tracking-tight text-white">User Settings</h1>
        {me ? (
          <p className="mt-1 text-sm/6 text-gray-400">
            Signed in as <strong className="font-semibold text-white">{me.username}</strong> ({me.role})
          </p>
        ) : null}
        {settings.error ? (
          <p className="mt-4 rounded-md bg-red-500/10 px-4 py-3 text-sm text-red-400 ring-1 ring-inset ring-red-500/20" role="alert">
            {settings.error}
          </p>
        ) : null}
      </header>

      <Card>
        <TokensSection
          me={me}
          isSuperuser={settings.isSuperuser}
          canCreateToken={settings.canCreateToken}
          repositories={settings.repositories}
          tokens={settings.tokens}
          setTokens={settings.setTokens}
          run={run}
        />
      </Card>

      {settings.isSuperuser ? (
        <>
          <Card>
            <RepositoriesSection
              repositories={settings.repositories}
              setRepositories={settings.setRepositories}
              run={run}
            />
          </Card>
          <Card>
            <UsersSection
              me={me}
              users={settings.users}
              repositories={settings.repositories}
              applyUserUpdate={settings.applyUserUpdate}
              run={run}
            />
          </Card>
          <Card>
            <TournamentsSection
              tournaments={settings.tournaments}
              setTournaments={settings.setTournaments}
              sources={settings.sources}
              run={run}
            />
          </Card>
        </>
      ) : null}
    </SettingsLayout>
  );
}
