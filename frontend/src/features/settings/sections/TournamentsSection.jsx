import { useState } from "react";

import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Select } from "../../../components/ui/Select";
import { EmptyRow, Table } from "../../../components/ui/Table";
import {
  createTournament,
  getTournamentSourceIds,
  updateTournament,
  updateTournamentSources,
} from "../../../lib/api/admin";
import { Hint, SectionTitle, SubsectionTitle } from "../components/Headings";
import { VisibilityToggle } from "../components/VisibilityToggle";
import { TOURNAMENT_PROVIDERS } from "../constants";
import { replaceById, sortByName, toggleId } from "../listUtils";

// A wrapping row: fields share the width, the switch and button keep their natural size.
const WIDE_FORM = "flex flex-wrap items-center gap-x-3 gap-y-2";
const WIDE_FIELD = "min-w-40 flex-1";

function ProviderOptions() {
  return TOURNAMENT_PROVIDERS.map((provider) => (
    <option key={provider.value || "none"} value={provider.value}>
      {provider.label}
    </option>
  ));
}

// Tournament series group sources (setups) under one name, optionally linked
// to a start.gg / parry.gg event that resolves the current tournament name.
export function TournamentsSection({ tournaments, setTournaments, sources, run }) {
  return (
    <>
      <SectionTitle>Tournament Series</SectionTitle>
      <CreateTournamentForm setTournaments={setTournaments} run={run} />
      <EditTournamentForm tournaments={tournaments} setTournaments={setTournaments} sources={sources} run={run} />
    </>
  );
}

function CreateTournamentForm({ setTournaments, run }) {
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("");
  const [slug, setSlug] = useState("");
  const [isPublic, setIsPublic] = useState(false);

  function onSubmit(event) {
    event.preventDefault();
    run(async () => {
      const created = await createTournament({
        name: name.trim(),
        is_public: isPublic,
        provider: provider || null,
        slug: slug.trim() || null,
      });
      setTournaments((prev) => sortByName([...prev, created]));
      setName("");
      setProvider("");
      setSlug("");
      setIsPublic(false);
    });
  }

  return (
    <>
      <SubsectionTitle
        title="New Tournament Series"
        description="Create a new series, optionally attach a provider slug, and set visibility."
      />
      <form className={WIDE_FORM} onSubmit={onSubmit}>
        <Input
          className={WIDE_FIELD}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="New tournament series name"
          aria-label="New tournament series name"
        />
        <Select className={WIDE_FIELD} value={provider} onChange={(event) => setProvider(event.target.value)} aria-label="Provider">
          <ProviderOptions />
        </Select>
        <Input
          className={WIDE_FIELD}
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="Tournament slug (optional)"
          aria-label="Tournament slug"
        />
        <VisibilityToggle active={isPublic} onToggle={() => setIsPublic((prev) => !prev)} />
        <Button type="submit">
          Create Tournament
        </Button>
      </form>
    </>
  );
}

function EditTournamentForm({ tournaments, setTournaments, sources, run }) {
  const [selectedId, setSelectedId] = useState("");
  const [sourceIds, setSourceIds] = useState([]);
  const [provider, setProvider] = useState("");
  const [slug, setSlug] = useState("");
  const [isPublic, setIsPublic] = useState(false);

  const selected = tournaments.find((tournament) => String(tournament.id) === String(selectedId)) || null;
  const disabled = !selectedId;

  function loadMetadata(tournament) {
    setProvider(tournament?.provider || "");
    setSlug(tournament?.slug || "");
    setIsPublic(Boolean(tournament?.is_public));
  }

  function onSelect(tournamentId) {
    setSelectedId(tournamentId);
    if (!tournamentId) {
      setSourceIds([]);
      loadMetadata(null);
      return;
    }
    loadMetadata(tournaments.find((tournament) => String(tournament.id) === String(tournamentId)));
    run(async () => setSourceIds(await getTournamentSourceIds(tournamentId)));
  }

  function onSaveSources() {
    run(() => updateTournamentSources(selectedId, sourceIds));
  }

  function onSaveMetadata() {
    run(async () => {
      const updated = await updateTournament(selectedId, {
        is_public: isPublic,
        provider: provider || null,
        slug: slug.trim() || null,
      });
      setTournaments((prev) => sortByName(replaceById(prev, updated)));
      loadMetadata(updated);
    });
  }

  return (
    <>
      <SubsectionTitle
        title="Save Existing Tournament Series"
        description="Select an existing series to update source assignments and metadata."
      />
      <div className="mb-2 flex gap-2">
        <Select className="flex-1" value={selectedId} onChange={(event) => onSelect(event.target.value)} aria-label="Tournament series">
          <option value="">Select tournament</option>
          {tournaments.map((tournament) => (
            <option key={tournament.id} value={tournament.id}>
              {tournament.name}
            </option>
          ))}
        </Select>
        <Button onClick={onSaveSources} disabled={disabled}>
          Save Sources
        </Button>
      </div>

      <div className={WIDE_FORM}>
        <Select
          className={WIDE_FIELD}
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
          disabled={disabled}
          aria-label="Provider"
        >
          <ProviderOptions />
        </Select>
        <Input
          className={WIDE_FIELD}
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="Tournament slug"
          aria-label="Tournament slug"
          disabled={disabled}
        />
        <VisibilityToggle active={isPublic} onToggle={() => setIsPublic((prev) => !prev)} disabled={disabled} />
        <Button onClick={onSaveMetadata} disabled={disabled}>
          Save Tournament Metadata
        </Button>
      </div>

      {selected ? (
        <Hint className="mt-3">Current resolved tournament name: {selected.current_tournament_name || "not resolved"}</Hint>
      ) : null}

      <Table className="mt-2" headers={["Use", "Source", "Owner", "Token Prefix"]}>
        {sources.length === 0 ? <EmptyRow colSpan={4}>No sources found.</EmptyRow> : null}
        {sources.map((source) => (
          <tr key={source.id}>
            <td>
              <input
                type="checkbox"
                className="size-4 cursor-pointer rounded-sm accent-indigo-500 disabled:cursor-not-allowed"
                checked={sourceIds.includes(source.id)}
                onChange={() => setSourceIds((prev) => toggleId(prev, source.id))}
                disabled={disabled}
                aria-label={`Use ${source.source_name}`}
              />
            </td>
            <td>{source.source_name}</td>
            <td>{source.username}</td>
            <td>{source.token_prefix}...</td>
          </tr>
        ))}
      </Table>
    </>
  );
}
