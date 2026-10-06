import { Link } from "react-router-dom";

import { useConsentContext } from "../ConsentContext";
import { ROUTES } from "../routes";
import type { Persona } from "../protocol";
import {
  CATEGORY_FILTER_LABELS,
  RANDOM_SCENARIO_ID,
  type CategoryFilter,
  type LibraryFilter,
  type ScenarioCard,
} from "../scenarioLibrary";
import LanguageFlag from "./LanguageFlag";
import LibraryPicker from "./LibraryPicker";
import { cx } from "../utils/cx";
import PersonaAvatar from "./PersonaAvatar";
import { ScenarioDescription } from "./ScenarioBriefing";
import SelectionSummary from "./SelectionSummary";
import SetupSection from "./SetupSection";

const NOT_SELECTED = "Noch nicht ausgewählt";

/** F-62: the choice, plus the category it will be drawn from. */
function randomSelectedLabel(category: CategoryFilter): string {
  return category === "all"
    ? "Zufallsszenario"
    : `Zufallsszenario ${CATEGORY_FILTER_LABELS[category]}`;
}

interface SetupViewProps {
  scenarioItems: ScenarioCard[];
  scenarioId: string | null;
  scenarioFilter: LibraryFilter;
  onScenarioFilter: (f: LibraryFilter) => void;
  /** Each counted against the other row, so an empty option shows in advance. */
  scenarioOriginCounts: Record<LibraryFilter, number>;
  scenarioCategory: CategoryFilter;
  onScenarioCategory: (c: CategoryFilter) => void;
  scenarioCategoryCounts: Record<CategoryFilter, number>;
  showRecommended: boolean;
  tenantName: string | null;
  onNewScenario: () => void;
  /** F-62. */
  offerRandom: boolean;
  /** Editing starts there (ADR 0062). */
  onShowScenarioInfo: (id: string) => void;
  personas: Persona[];
  personaId: string | null;
  onShowPersonaInfo: (id: string) => void;
  selectedScenario: ScenarioCard | null;
  selectedPersona: Persona | null;
  loadError: string | null;
  onSelectScenario: (id: string) => void;
  onSelectPersona: (id: string) => void;
  onStart: () => void;
}

/** Presentational: only the final button commits a Session (ADR 0042). */
export default function SetupView({
  scenarioItems,
  scenarioId,
  scenarioFilter,
  onScenarioFilter,
  scenarioOriginCounts,
  scenarioCategory,
  onScenarioCategory,
  scenarioCategoryCounts,
  showRecommended,
  tenantName,
  onNewScenario,
  offerRandom,
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
  // Drawn on the way into the call (F-62).
  const randomPicked = scenarioId === RANDOM_SCENARIO_ID;

  return (
    <>
      <section className="setup-intro" aria-labelledby="setup-page-title">
        <h1 id="setup-page-title">Wählen Sie Ihr Kundengespräch</h1>

        <p className="setup-intro-description">
          Wählen Sie die Gesprächssituation und den passenden Gesprächspartner. Sprache und
          Stimme übernimmt die ausgewählte Persona.
        </p>
      </section>

      <SetupSection
        index="1"
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
          showRecommended={showRecommended}
          tenantName={tenantName}
          newLabel="+ Individuelles Szenario"
          onNew={onNewScenario}
          offerRandom={offerRandom}
          onInfo={onShowScenarioInfo}
        />
      </SetupSection>

      <SetupSection
        index="2"
        title="Gesprächspartner wählen"
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
              avatarUrl={persona.avatar_url}
              isSelected={persona.id === personaId}
              onSelect={() => onSelectPersona(persona.id)}
              onInfo={() => onShowPersonaInfo(persona.id)}
              infoLabel={`Mehr über ${persona.name}`}
            />
          ))}
        </div>
      </SetupSection>

      <SetupSection index="3" title="Auswahl prüfen" description="Ihre Trainingsauswahl steht fest.">
        <SelectionSummary
          scenario={
            randomPicked
              ? randomSelectedLabel(scenarioCategory)
              : selectedScenario?.name ?? NOT_SELECTED
          }
          persona={selectedPersona?.name ?? NOT_SELECTED}
          language={selectedPersona?.language ?? NOT_SELECTED}
        />

        {/* The Wissensstand follows after the mic check (ADR 0054). */}
        <ScenarioDescription description={selectedScenario?.description} />

        {/* Before the call, while the user can still change their mind (ADR 0066). */}
        {consent && !consent.allows_storage && (
          <p className="setup-storage-note">
            Dieses Training wird <strong>nicht gespeichert</strong>. Sie sehen das
            Gesprächsprotokoll direkt im Anschluss. Eine Auswertung gibt es nicht, und in Ihrer
            Trainingshistorie erscheint das Gespräch später nicht.{" "}
            <Link to={ROUTES.profile}>Im Profil ändern</Link>
          </p>
        )}

        <button
          className="start-call-button setup-start-button"
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

/** The Persona step's card. The "i" sits beside the card button (buttons cannot nest); reading does not select. */
function ChoiceCard({
  title,
  subtitle,
  language,
  languageCode,
  avatarUrl,
  isSelected,
  onSelect,
  onInfo,
  infoLabel,
}: {
  title: string;
  subtitle: string;
  language: string;
  languageCode: string;
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
          {/* Before the language word, so every flag sits at the same x. */}
          <span className="card-meta">
            <LanguageFlag code={languageCode} />
            {language}
          </span>
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
