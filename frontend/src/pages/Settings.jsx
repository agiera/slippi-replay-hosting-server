import { Card } from "../components/ui/Card";
import { Hint } from "../features/settings/components/Headings";
import { useSettingsData } from "../features/settings/hooks/useSettingsData";
import { RepositoriesSection } from "../features/settings/sections/RepositoriesSection";
import { TokensSection } from "../features/settings/sections/TokensSection";
import { TournamentsSection } from "../features/settings/sections/TournamentsSection";
import { UsersSection } from "../features/settings/sections/UsersSection";

function SettingsLayout({ children }) {
  return (
    <main className="grid min-h-[calc(100vh-46px)] content-start justify-items-center gap-3.5 p-6 [&>section]:max-w-[960px]">
      {children}
    </main>
  );
}

export default function Settings() {
  const settings = useSettingsData();
  const { me, run } = settings;

  if (settings.loading) {
    return (
      <SettingsLayout>
        <Card>
          <p className="my-0">Loading settings...</p>
        </Card>
      </SettingsLayout>
    );
  }

  return (
    <SettingsLayout>
      <Card>
        <h1 className="mt-0 mb-3 text-[2rem] leading-tight font-bold">User Settings</h1>
        {me ? (
          <Hint>
            Signed in as <strong className="text-fg">{me.username}</strong> ({me.role})
          </Hint>
        ) : null}
        {settings.error ? (
          <p className="mt-0 mb-4 text-danger" role="alert">
            {settings.error}
          </p>
        ) : null}

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
        <Card>
          <RepositoriesSection
            repositories={settings.repositories}
            setRepositories={settings.setRepositories}
            run={run}
          />
          <UsersSection
            me={me}
            users={settings.users}
            repositories={settings.repositories}
            applyUserUpdate={settings.applyUserUpdate}
            run={run}
          />
          <TournamentsSection
            tournaments={settings.tournaments}
            setTournaments={settings.setTournaments}
            sources={settings.sources}
            run={run}
          />
        </Card>
      ) : null}
    </SettingsLayout>
  );
}
