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

const WIDE_FORM = "mb-2.5 grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-2";

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
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="New tournament series name"
          aria-label="New tournament series name"
        />
        <Select value={provider} onChange={(event) => setProvider(event.target.value)} aria-label="Provider">
          <ProviderOptions />
        </Select>
        <Input
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="Tournament slug (optional)"
          aria-label="Tournament slug"
        />
        <VisibilityToggle active={isPublic} onToggle={() => setIsPublic((prev) => !prev)} />
        <Button type="submit" size="lg">
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
      <div className="mb-2.5 grid grid-cols-[1fr_auto] gap-2">
        <Select value={selectedId} onChange={(event) => onSelect(event.target.value)} aria-label="Tournament series">
          <option value="">Select tournament</option>
          {tournaments.map((tournament) => (
            <option key={tournament.id} value={tournament.id}>
              {tournament.name}
            </option>
          ))}
        </Select>
        <Button size="lg" onClick={onSaveSources} disabled={disabled}>
          Save Sources
        </Button>
      </div>

      <div className={WIDE_FORM}>
        <Select
          value={provider}
          onChange={(event) => setProvider(event.target.value)}
          disabled={disabled}
          aria-label="Provider"
        >
          <ProviderOptions />
        </Select>
        <Input
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="Tournament slug"
          aria-label="Tournament slug"
          disabled={disabled}
          className="disabled:cursor-not-allowed disabled:opacity-65"
        />
        <VisibilityToggle active={isPublic} onToggle={() => setIsPublic((prev) => !prev)} disabled={disabled} />
        <Button size="lg" onClick={onSaveMetadata} disabled={disabled}>
          Save Tournament Metadata
        </Button>
      </div>

      {selected ? (
        <Hint>Current resolved tournament name: {selected.current_tournament_name || "not resolved"}</Hint>
      ) : null}

      <Table headers={["Use", "Source", "Owner", "Token Prefix"]}>
        {sources.length === 0 ? <EmptyRow colSpan={4}>No sources found.</EmptyRow> : null}
        {sources.map((source) => (
          <tr key={source.id}>
            <td>
              <input
                type="checkbox"
                className="m-0 cursor-pointer disabled:cursor-not-allowed"
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
