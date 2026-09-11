import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { ROUTES } from "../routes";
import type { Persona } from "../protocol";
import type { ScenarioCard } from "../scenarioLibrary";
import LibraryPicker, {
  type CategoryFilter,
  type LibraryFilter,
  type LibraryItem,
} from "./LibraryPicker";
import { cx } from "../utils/cx";
import PersonaAvatar from "./PersonaAvatar";
import ScenarioBriefing from "./ScenarioBriefing";
import SelectionSummary from "./SelectionSummary";
import SetupSection from "./SetupSection";

const NOT_SELECTED = "Noch nicht ausgewählt";

interface SetupViewProps {
  scenarioItems: LibraryItem[];
  scenarioId: string | null;
  scenarioFilter: LibraryFilter;
  onScenarioFilter: (f: LibraryFilter) => void;
  /** How many Scenarios each option of a row would show, counted against the
   * *other* row only. Switching to an empty option is then visible in advance
   * rather than a surprise. */
  scenarioOriginCounts: Record<LibraryFilter, number>;
  scenarioCategory: CategoryFilter;
  onScenarioCategory: (c: CategoryFilter) => void;
  scenarioCategoryCounts: Record<CategoryFilter, number>;
  tenantName: string | null;
  onNewScenario: () => void;
  /** Open a Scenario's read-only info panel; editing starts there
   * (ADR 0076). */
  onShowScenarioInfo: (id: string) => void;
  personas: Persona[];
  personaId: string | null;
  /** Open the read-only info panel for this Persona. Held in App.tsx
   * beside the Scenario editor's state, since this component keeps none. */
  onShowPersonaInfo: (id: string) => void;
  selectedScenario: ScenarioCard | null;
  selectedPersona: Persona | null;
  loadError: string | null;
  onSelectScenario: (id: string) => void;
  onSelectPersona: (id: string) => void;
  onStart: () => void;
}

/**
 * Presentational: the three-step selection screen. A Session is committed to
 * only by the button at the end — picking a Persona or Scenario connects
 * nothing (ADR 0042), which is why this component holds no state of its own
 * beyond what App.tsx passes in (the Scenario filter and library included,
 * ADR 0058/0060).
 */
export default function SetupView({
  scenarioItems,
  scenarioId,
  scenarioFilter,
  onScenarioFilter,
  scenarioOriginCounts,
  scenarioCategory,
  onScenarioCategory,
  scenarioCategoryCounts,
  tenantName,
  onNewScenario,
  onShowScenarioInfo,
  personas,
  personaId,
  onShowPersonaInfo,
  selectedScenario,
  selectedPersona,
  loadError,
  onSelectScenario,
  onSelectPersona,
  onStart,
}: SetupViewProps) {
  const { consent } = useConsentContext();

  return (
    <>
      <section className="setup-intro" aria-labelledby="setup-page-title">
        <div className="eyebrow">Training vorbereiten</div>

        <h1 id="setup-page-title">Wählen Sie Ihr Kundengespräch</h1>

        <p className="setup-intro-description">
          Wählen Sie die Gesprächssituation und den passenden Gesprächspartner. Sprache und
          Stimme übernimmt die ausgewählte Persona.
        </p>
      </section>

      <SetupSection
        index="01"
        title="Gesprächssituation wählen"
        description="Welche Situation möchten Sie trainieren?"
      >
        <LibraryPicker
          items={scenarioItems}
          selectedId={scenarioId}
          onSelect={onSelectScenario}
          filter={scenarioFilter}
          onFilter={onScenarioFilter}
          originCounts={scenarioOriginCounts}
          category={scenarioCategory}
          onCategory={onScenarioCategory}
          categoryCounts={scenarioCategoryCounts}
          tenantName={tenantName}
          newLabel="+ Individuelles Szenario"
          onNew={onNewScenario}
          onInfo={onShowScenarioInfo}
        />
      </SetupSection>

      <SetupSection
        index="02"
        title="Gesprächspartner auswählen"
        description="Jede Persona besitzt eine eigene Sprache, Stimme und Persönlichkeit."
      >
        <div className="persona-grid setup-persona-grid">
          {personas.map((persona) => (
            <ChoiceCard
              key={persona.id}
              title={persona.name}
              subtitle={persona.role}
              language={persona.language}
              avatarUrl={persona.avatar_url}
              isSelected={persona.id === personaId}
              onSelect={() => onSelectPersona(persona.id)}
              onInfo={() => onShowPersonaInfo(persona.id)}
              infoLabel={`Mehr über ${persona.name}`}
            />
          ))}
        </div>
      </SetupSection>

      <SetupSection index="03" title="Auswahl prüfen" description="Ihre Trainingsauswahl steht fest.">
        <SelectionSummary
          scenario={selectedScenario?.name ?? NOT_SELECTED}
          persona={selectedPersona?.name ?? NOT_SELECTED}
          language={selectedPersona?.language ?? NOT_SELECTED}
          voice="Durch Persona festgelegt"
        />

        {/* The trainee's side of the case (ADR 0054). Here as well as on the
            microphone check: which Scenario to pick is itself a decision, and
            the card's one line says only what the caller wants. */}
        <ScenarioBriefing briefing={selectedScenario?.briefing} />

        {/* Said before the call, not after it (ADR 0066). Someone who declined
            storage should learn that this training will leave no record while
            they can still change their mind — finding out afterwards, with the
            transcript already gone, is finding out too late. */}
        {consent && !consent.allows_storage && (
          <p className="setup-storage-note">
            Dieses Training wird <strong>nicht gespeichert</strong>. Sie sehen das
            Gesprächsprotokoll direkt im Anschluss. Eine Auswertung gibt es nicht, und in Ihrer
            Trainingshistorie erscheint das Gespräch später nicht.{" "}
            <Link to={ROUTES.profile}>Im Profil ändern</Link>
          </p>
        )}

        <button
          className="start-call-button"
          type="button"
          disabled={selectedPersona === null || selectedScenario === null}
          onClick={onStart}
        >
          Weiter zum Mikrofontest
        </button>
      </SetupSection>

      {loadError && (
        <p id="status" className="error">
          {loadError}
        </p>
      )}
    </>
  );
}

/** One selectable card. The Persona step is a plain grid (Personas are
 * curated, not User-authored); the Scenario step uses LibraryPicker instead,
 * which adds filtering and authoring.
 *
 * The info affordance sits *outside* the card button rather than inside it —
 * a button cannot be nested in a button — using the same `card-wrap` shell
 * LibraryPicker puts its "Bearbeiten" link in. Reading about a Persona and
 * choosing one are separate acts: the "i" does not select the card.
 *
 * The portrait sits left of the text, which is why the three lines are wrapped
 * in an element of their own: the card is a row, and they are its second
 * column. */
function ChoiceCard({
  title,
  subtitle,
  language,
  avatarUrl,
  isSelected,
  onSelect,
  onInfo,
  infoLabel,
}: {
  title: string;
  subtitle: string;
  language: string;
  avatarUrl: string | null;
  isSelected: boolean;
  onSelect: () => void;
  onInfo: () => void;
  infoLabel: string;
}) {
  return (
    <div className="card-wrap">
      <button
        type="button"
        className={cx("persona-card", isSelected && "selected")}
        aria-pressed={isSelected}
        onClick={onSelect}
      >
        <span className="choice-check" aria-hidden="true">
          {isSelected ? "✓" : ""}
        </span>

        <PersonaAvatar name={title} src={avatarUrl} className="persona-card-portrait" />

        <span className="persona-card-body">
          <span className="persona-name">{title}</span>
          <span className="card-subtitle">{subtitle}</span>
          <span className="card-meta">{language}</span>
        </span>
      </button>

      <button
        type="button"
        className="card-info"
        onClick={onInfo}
        aria-label={infoLabel}
        title={infoLabel}
      >
        <span aria-hidden="true">i</span>
      </button>
    </div>
  );
}
