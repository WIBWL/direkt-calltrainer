import type { Persona } from "../protocol";
import type { ScenarioCard } from "../scenarioLibrary";
import LibraryPicker, { type LibraryFilter, type LibraryItem } from "./LibraryPicker";
import { cx } from "../utils/cx";
import SelectionSummary from "./SelectionSummary";
import SetupSection from "./SetupSection";

const NOT_SELECTED = "Noch nicht ausgewählt";

interface SetupViewProps {
  scenarioItems: LibraryItem[];
  scenarioId: string | null;
  scenarioFilter: LibraryFilter;
  onScenarioFilter: (f: LibraryFilter) => void;
  showScenarioFilter: boolean;
  companyLabel: string | null;
  onNewScenario: () => void;
  onEditScenario: (id: string) => void;
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
  showScenarioFilter,
  companyLabel,
  onNewScenario,
  onEditScenario,
  personas,
  personaId,
  selectedScenario,
  selectedPersona,
  loadError,
  onSelectScenario,
  onSelectPersona,
  onStart,
}: SetupViewProps) {
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
          showFilter={showScenarioFilter}
          filterLabel="Szenarien filtern"
          companyLabel={companyLabel}
          newLabel="+ Eigenes Szenario"
          onNew={onNewScenario}
          onEdit={onEditScenario}
        />
      </SetupSection>

      <SetupSection
        index="02"
        title="Gesprächspartner auswählen"
        description="Jede Persona besitzt eine eigene Sprache, Stimme und Persönlichkeit."
      >
        <div className="persona-grid">
          {personas.map((persona) => (
            <ChoiceCard
              key={persona.id}
              title={persona.name}
              subtitle={persona.role}
              isSelected={persona.id === personaId}
              onSelect={() => onSelectPersona(persona.id)}
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
 * which adds filtering and authoring. */
function ChoiceCard({
  title,
  subtitle,
  isSelected,
  onSelect,
}: {
  title: string;
  subtitle: string;
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

      <span className="persona-name">{title}</span>
      <span className="card-subtitle">{subtitle}</span>
    </button>
  );
}
