import { useState, type ReactNode } from "react";

import { ApiError } from "../api";
import type { FollowUpCard } from "../protocol";
import { createFollowUp, createReverse, type ReverseScenario } from "../scenarioLibrary";
import { cx } from "../utils/cx";

/** What a screen can do with the follow-up Scenario (F-60), passed in by its owner. No
 * edit: the write routes refuse a follow-up (ADR 0069); deletion is in the info panel.
 * `onStart` gets the Persona too, since the follow-up keeps the training's partner.
 * `onCreated` fires once one was written, so the screen's library copy can reload. */
export interface FollowUpActions {
  onStart: (scenarioId: string, personaId: string) => void;
  onCreated?: (() => void) | undefined;
}

/**
 * One press that writes a Scenario out of this Session — follow-up or reverse (ADR 0069,
 * ADR 0070). The backend's `detail` is shown as is, `fallback` where there is none. `run`
 * resolves to what was written, or null on failure.
 */
function useCreate<T>(create: () => Promise<T>, fallback: string) {
  const [created, setCreated] = useState<T | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (): Promise<T | null> => {
    setBusy(true);
    setError(null);
    try {
      const result = await create();
      setCreated(result);
      return result;
    } catch (e: unknown) {
      setError(e instanceof ApiError && e.detail ? e.detail : fallback);
      return null;
    } finally {
      setBusy(false);
    }
  };

  return { created, busy, error, run };
}

/** The frame both offers share, before and after their Scenario is written:
 *  title, one lead paragraph, and whatever the offer is right now. */
function NextStepCard({
  title,
  lead,
  className,
  children,
}: {
  title: string;
  lead: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cx("card next-step", className)}>
      <h2 className="next-step-title">{title}</h2>
      <p className="next-step-lead">{lead}</p>
      {children}
    </section>
  );
}

/** The first press: the button that writes the Scenario, and what to say while
 *  that runs or after it failed. */
function CreateButton({
  label,
  busyLabel,
  busyNote,
  busy,
  error,
  onClick,
}: {
  label: string;
  busyLabel: string;
  busyNote: string;
  busy: boolean;
  error: string | null;
  onClick: () => void;
}) {
  return (
    <>
      <button type="button" className="follow-up-button" disabled={busy} onClick={onClick}>
        {busy ? busyLabel : label}
      </button>
      {busy && <p className="follow-up-note">{busyNote}</p>}
      {error && <p className="follow-up-error">{error}</p>}
    </>
  );
}

/** The second press: the written Scenario, named, and the button that starts
 *  it. The button sits in its own row wrapper — that is where the space above
 *  it comes from, so both offers are spaced alike without the number being
 *  written twice. */
function StartCreated({
  name,
  teaser,
  note,
  onStart,
}: {
  name: string;
  teaser: string;
  note: string;
  onStart: () => void;
}) {
  return (
    <>
      <p className="follow-up-name">{name}</p>
      <p className="follow-up-teaser">{teaser}</p>
      <div className="follow-up-actions">
        <button type="button" className="follow-up-button" onClick={onStart}>
          Starten
        </button>
      </div>
      <p className="follow-up-note">{note}</p>
    </>
  );
}

/** The next call in the same matter, built from the points above (F-60). Asked for by
 * the User (ADR 0069's amendment); the same card renders the offer and the written row.
 * Starting skips the mic check and uses this training's Persona; another partner means
 * starting it from the setup screen. */
export function FollowUp({
  scenario,
  personaId,
  sessionId,
  onStart,
  onCreated,
}: {
  scenario: FollowUpCard | null;
  personaId: string;
  sessionId: string;
} & FollowUpActions) {
  const create = useCreate(
    () => createFollowUp(sessionId),
    "Das Folgeszenario konnte nicht erstellt werden.",
  );
  // What the create route just wrote, so the card appears without waiting for
  // a refetch. `scenario` wins: on a reload it is the same row, and on the
  // history's page it is the only source.
  const card = scenario ?? create.created;

  if (!card) {
    return (
      <NextStepCard
        title="Folgeszenario"
        lead="Daraus lässt sich Ihr nächstes Gespräch bauen: derselbe Fall, einige Zeit später – diesmal so, dass genau das nötig ist, was hier gefehlt hat."
      >
        <CreateButton
          label="Folgeszenario erstellen"
          busyLabel="Folgeszenario wird gebaut …"
          busyNote="Die Übung wird gerade geschrieben – das dauert einen Moment."
          busy={create.busy}
          error={create.error}
          onClick={() =>
            void create.run().then((written) => {
              if (written) onCreated?.();
            })
          }
        />
      </NextStepCard>
    );
  }

  return (
    <NextStepCard
      title="Folgeszenario"
      lead="Daraus ist Ihr nächstes Gespräch entstanden: derselbe Fall, einige Zeit später – diesmal so, dass genau das nötig ist, was hier gefehlt hat. Es liegt unter „Folgeszenario“ in Ihrer Auswahl."
    >
      <StartCreated
        name={card.name}
        teaser={card.short_description}
        onStart={() => onStart(card.id, personaId)}
        note="„Starten“ ruft denselben Gesprächspartner wie in diesem Training an – ohne Mikrofoncheck. Das Gespräch beginnt, sobald Sie den Anruf annehmen."
      />
    </NextStepCard>
  );
}

/** The Reverse offer (F-61, ADR 0070): the same call from the other side. Two presses,
 * like the follow-up: the first writes the Scenario (a model call, most of a minute), the
 * second begins the call, so the start button is never the one pressed before there was
 * anything to start. The Scenario is stored either way. */
export function Reverse({
  sessionId,
  onReverse,
}: {
  sessionId: string;
  onReverse: (reverse: ReverseScenario) => void;
}) {
  const create = useCreate(
    () => createReverse(sessionId),
    "Der Rollentausch konnte nicht vorbereitet werden.",
  );
  const created = create.created;

  if (created) {
    return (
      <NextStepCard
        title="Rollentausch"
        className="reverse-offer"
        lead="Ihr Rollentausch ist vorbereitet. Sie bekommen vor dem Gespräch die Unterlagen zu sehen, die die KI eben hatte."
      >
        <StartCreated
          name={created.name}
          teaser={created.short_description}
          onStart={() => onReverse(created)}
          note="Sie rufen an, die KI nimmt ab — mit demselben Gesprächspartner wie in diesem Training."
        />
      </NextStepCard>
    );
  }

  return (
    <NextStepCard
      title="Rollentausch"
      className="reverse-offer"
      lead="Erleben Sie dasselbe Gespräch von der anderen Seite: Sie rufen an, die KI nimmt ab. Was die KI eben wusste, sehen währenddessen Sie."
    >
      <CreateButton
        label="Rollen tauschen"
        busyLabel="Rollentausch wird vorbereitet …"
        busyNote="Ihre Unterlagen für das Gespräch werden zusammengestellt — das dauert einen Moment."
        busy={create.busy}
        error={create.error}
        onClick={() => void create.run()}
      />
    </NextStepCard>
  );
}
