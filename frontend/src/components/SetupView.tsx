import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { ROUTES } from "../routes";
import type { Persona } from "../protocol";
import { RANDOM_SCENARIO_ID, type ScenarioCard } from "../scenarioLibrary";
import LanguageFlag from "./LanguageFlag";
import LibraryPicker, {
  type CategoryFilter,
  type LibraryFilter,
  type LibraryItem,
} from "./LibraryPicker";
import { cx } from "../utils/cx";
import SelectionSummary from "./SelectionSummary";
import SetupSection from "./SetupSection";

const NOT_SELECTED = "Noch nicht ausgewählt";

/** What the summary can honestly say about a case that has not been drawn yet
 * (F-62). It names the choice that was made without naming its outcome — which
 * is the whole of what the User is agreeing to here. */
const RANDOM_SELECTED = "Zufallsszenario – wird beim Start gezogen";

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
  onEditScenario: (id: string) => void;
  /** Retire a reverse (ADR 0070); the only affordance it has. */
  onRemoveScenario: (id: string) => void;
  /** Whether there is anything in the library to draw a Zufallsszenario from
   * (F-62). */
  offerRandom: boolean;
  personas: Persona[];
  personaId: string | null;
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
  onEditScenario,
  onRemoveScenario,
  offerRandom,
  personas,
  personaId,
  selectedScenario,
  selectedPersona,
  loadError,
  onSelectScenario,
  onSelectPersona,
  onStart,
}: SetupViewProps) {
  const { consent } = useConsentContext();
  // The one selection that resolves to no card: it is drawn on the way into
  // the call, not here (F-62).
  const randomPicked = scenarioId === RANDOM_SCENARIO_ID;

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
          onEdit={onEditScenario}
          onRemove={onRemoveScenario}
          offerRandom={offerRandom}
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
              languageCode={persona.language_code}
              isSelected={persona.id === personaId}
              onSelect={() => onSelectPersona(persona.id)}
            />
          ))}
        </div>
      </SetupSection>

      <SetupSection index="03" title="Auswahl prüfen" description="Ihre Trainingsauswahl steht fest.">
        <SelectionSummary
          scenario={
            randomPicked ? RANDOM_SELECTED : selectedScenario?.name ?? NOT_SELECTED
          }
          persona={selectedPersona?.name ?? NOT_SELECTED}
          language={selectedPersona?.language ?? NOT_SELECTED}
        />

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
          disabled={selectedPersona === null || (selectedScenario === null && !randomPicked)}
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
 * which adds filtering and authoring. */
function ChoiceCard({
  title,
  subtitle,
  language,
  languageCode,
  isSelected,
  onSelect,
}: {
  title: string;
  subtitle: string;
  language: string;
  /** Which flag goes beside the name; the language stays as text below it. */
  languageCode: string;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={cx("persona-card", isSelected && "selected")}
      aria-pressed={isSelected}
      onClick={onSelect}
    >
      <span className="choice-check" aria-hidden="true">
        {isSelected ? "✓" : ""}
      </span>

      <span className="persona-name-row">
        <span className="persona-name">{title}</span>
        <LanguageFlag code={languageCode} />
      </span>
      <span className="card-subtitle">{subtitle}</span>
      <span className="card-meta">{language}</span>
    </button>
  );
}
