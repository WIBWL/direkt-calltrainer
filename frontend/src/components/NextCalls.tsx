import { useFocusContext } from "../FocusContext";
import type { NextCallOffer } from "../scenarioLibrary";
import { recommendationReason } from "./LibraryPicker";

/**
 * What to play next (F-64): Scenarios that already exist, one press to start.
 *
 * Unlike the follow-up and the reverse beside it, nothing is written first, so
 * "Starten" begins the call at once — skipping the microphone check, which was
 * in use seconds ago. Each offer names its reason.
 */
export default function NextCalls({
  offers,
  onStart,
}: {
  offers: NextCallOffer[] | null;
  onStart: (scenarioId: string, personaId: string) => void;
}) {
  const { focus } = useFocusContext();
  if (!offers || offers.length === 0) return null;
  const goalTitle = (key: string) => focus?.goals.find((g) => g.key === key)?.title ?? key;

  return (
    <section className="card next-calls" aria-labelledby="next-calls-title">
      <div className="next-step-eyebrow">ALS NÄCHSTES</div>
      <h2 className="next-step-title" id="next-calls-title">Aus Ihrer Bibliothek</h2>
      <ul className="next-calls-list">
        {offers.map((offer) => (
          <li key={offer.kind} className="next-call">
            <span className="next-call-text">
              <span className="next-call-title">{title(offer)}</span>
              <span className="next-call-reason">{reason(offer, goalTitle)}</span>
            </span>
            <button
              type="button"
              className="follow-up-button"
              onClick={() => onStart(offer.scenario_id, offer.persona_id)}
            >
              Starten
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function title(offer: NextCallOffer): string {
  if (offer.kind === "language") return `Dasselbe Szenario auf ${offer.language}`;
  return offer.unplayed ? `Neues Szenario: ${offer.scenario_name}` : offer.scenario_name;
}

function reason(offer: NextCallOffer, goalTitle: (key: string) => string): string {
  if (offer.kind === "language") return `${offer.scenario_name} mit ${offer.persona_name}`;
  const parts = [
    offer.recommendation
      ? recommendationReason(offer.recommendation, goalTitle)
      : "Aus derselben Kategorie",
  ];
  if (offer.unplayed) parts.push("noch nicht gespielt");
  return parts.filter(Boolean).join(" · ");
}
