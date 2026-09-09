import type { Measurement } from "../protocol";
import PitchContour from "./PitchContour";

/**
 * What a speaker's pitch contour says about their delivery (F-35).
 *
 * Four factors rather than one figure, because one figure cannot separate a
 * speaker who was lively throughout from one who said a single sentence
 * brightly, nor one who closes their sentences from one who ends every second
 * one on a rise. `backend/feedback/intonation.py` derives them.
 *
 * Where the reading is allowed to interpret, and where it is not:
 *
 * The range and the movement are reported as figures with no adjective. There
 * is no validated norm for either in this population, so calling a number
 * "gut" or even "eng" would be inventing the threshold ADR 0051 declined to
 * invent, and the reader would rightly take it as measured.
 *
 * The endings are different, and they are where the substance of this reading
 * sits. Whether a sentence ends falling or rising has a natural zero, needs no
 * population norm, and what the two conventionally signal is among the
 * better-established findings about intonation. The wording still stops short
 * of a verdict: it says what the pattern typically sounds like to a listener,
 * and leaves the judgement of whether that was the intention to the speaker.
 *
 * The development across the call is a comparison of the speaker with
 * themselves, which is the one comparison available without a norm.
 */

/** Below this a change between the first and last third is wobble, not a
 *  development worth a sentence. Three semitones is a minor third. */
const NOTABLE_CHANGE_ST = 3;

interface Endings {
  falling: number;
  rising: number;
  level: number;
}

export default function IntonationReading({ measurement }: { measurement: Measurement }) {
  const detail = measurement.detail ?? {};
  const curve = detail.curve_hz as (number | null)[] | undefined;
  const median = detail.median_hz as number | undefined;
  const stepMs = (detail.curve_step_ms as number | undefined) ?? 100;
  const movement = detail.movement_st_per_s as number | undefined;
  const endings = detail.endings as Endings | undefined;
  const first = detail.range_first_st as number | undefined;
  const last = detail.range_last_st as number | undefined;

  // A Session measured before the factors existed carries the range and
  // nothing else. Its recording is long gone (ADR 0048), so the rest cannot be
  // reconstructed; the block says so rather than showing empty rows.
  if (!curve || !median) {
    return (
      <div className="card">
        <p className="muted">
          Für dieses Training liegt nur der Umfang vor. Der Tonhöhenverlauf wurde damals noch
          nicht mitgeschrieben, und die Aufnahme ist gelöscht, wie bei jedem Gespräch.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <PitchContour
          curveHz={curve}
          medianHz={median}
          stepMs={stepMs}
          bandLowSt={-measurement.value / 2}
          bandHighSt={measurement.value / 2}
        />
      </div>

      <h2>Vier Größen aus diesem Verlauf</h2>
      <div className="card">
        <dl className="factor-list">
          <Factor
            name="Umfang"
            value={`${measurement.value.toFixed(1)} Halbtöne`}
            explanation={
              `Zwischen Ihrem tiefsten und höchsten üblichen Ton liegt das ` +
              `${Math.pow(2, measurement.value / 12).toFixed(2)}-fache der Frequenz. ` +
              `Das ist eine Spanne, keine Lage: Ihre mittlere Stimmlage liegt bei ` +
              `${Math.round(median)} Hz und geht in diese Zahl nicht ein.`
            }
          />

          {movement !== undefined && (
            <Factor
              name="Bewegung"
              value={`${movement.toFixed(1)} Halbtöne pro Sekunde`}
              explanation={
                "Wie viel sich Ihre Stimme bewegt, während Sie sprechen. Zusammen mit dem " +
                "Umfang trennt das zwei sehr verschiedene Sprechweisen: Man kann eine weite " +
                "Spanne erreichen, indem man langsam von hoch nach tief driftet, und dieselbe " +
                "Spanne, indem man in jedem Satz arbeitet."
              }
            />
          )}

          {endings && endings.falling + endings.rising + endings.level > 0 && (
            <Factor
              name="Satzenden"
              value={endingsValue(endings)}
              explanation={endingsReading(endings)}
            />
          )}

          {first !== undefined && last !== undefined && (
            <Factor
              name="Verlauf über das Gespräch"
              value={`${first.toFixed(1)} → ${last.toFixed(1)} Halbtöne`}
              explanation={developmentReading(first, last)}
            />
          )}
        </dl>
      </div>
    </>
  );
}

function Factor({
  name,
  value,
  explanation,
}: {
  name: string;
  value: string;
  explanation: string;
}) {
  return (
    <div className="factor">
      <dt>
        <span className="factor-name">{name}</span>
        <span className="factor-value">{value}</span>
      </dt>
      <dd>{explanation}</dd>
    </div>
  );
}

function endingsValue({ falling, rising, level }: Endings): string {
  const parts = [`${falling} fallend`, `${rising} steigend`, `${level} gleichbleibend`];
  return parts.join(", ");
}

/**
 * The one place this screen interprets rather than reports.
 *
 * A final fall closes a statement; a final rise leaves it open, asks, or seeks
 * agreement. Neither is a fault, and the wording says so: what is worth
 * noticing is a mismatch between what somebody meant and how it landed, and
 * only the speaker can settle that.
 */
function endingsReading({ falling, rising, level }: Endings): string {
  const total = falling + rising + level;
  const base =
    "Eine fallende Endung schließt eine Aussage ab, eine steigende lässt sie offen, " +
    "fragt oder sucht Zustimmung. Keines von beidem ist für sich genommen richtig " +
    "oder falsch. ";

  if (rising > falling) {
    return (
      base +
      `Bei Ihnen endete die Mehrheit steigend (${rising} von ${total}). Auf Ihr Gegenüber ` +
      "kann das offen und einladend wirken, bei sachlichen Aussagen aber auch unsicherer, " +
      "als Sie es meinten. Hören Sie sich die Stellen an und entscheiden Sie selbst, ob es " +
      "so gemeint war."
    );
  }
  if (falling > rising) {
    return (
      base +
      `Bei Ihnen endete die Mehrheit fallend (${falling} von ${total}). Das wirkt ` +
      "abschließend und bestimmt. Wo Sie eine Frage gestellt oder zum Weiterreden eingeladen " +
      "haben, lohnt der Blick, ob die Melodie das mitgetragen hat."
    );
  }
  return (
    base +
    `Bei Ihnen hielten sich fallende und steigende Endungen die Waage (${falling} zu ${rising}).`
  );
}

/** A comparison of the speaker with themselves, which is the only comparison
 *  available here without a norm. */
function developmentReading(first: number, last: number): string {
  const change = last - first;
  if (Math.abs(change) < NOTABLE_CHANGE_ST) {
    return (
      "Ihr Tonhöhenumfang war am Ende des Gesprächs ungefähr so weit wie am Anfang. Die " +
      "Zahlen vergleichen das erste und das letzte Drittel Ihrer Sprechzeit, nicht der Uhr."
    );
  }
  if (change < 0) {
    return (
      `Gegen Ende wurde Ihre Melodie enger, um ${Math.abs(change).toFixed(1)} Halbtöne. Das ` +
      "passiert häufig, wenn ein Gespräch anstrengend wird oder wenn zum Schluss nur noch " +
      "Formalien abgearbeitet werden. Ob es hier so war, wissen Sie besser als die Messung."
    );
  }
  return (
    `Gegen Ende wurde Ihre Melodie weiter, um ${change.toFixed(1)} Halbtöne. Verglichen ` +
    "werden das erste und das letzte Drittel Ihrer Sprechzeit, nicht der Uhr."
  );
}
