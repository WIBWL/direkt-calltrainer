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
 * The range carries the five-step reading (stark monoton … überzeichnet), and
 * that step is a judgement on thresholds nothing has validated for this
 * population — the exception ADR 0051 does not cover, kept to this screen and
 * always shown with the scale it came from and the word "Einschätzung" beside
 * it. `backend/feedback/intonation.py` holds the boundaries and says where the
 * numbers come from.
 *
 * The movement is reported as a figure with no adjective, for the reason the
 * range no longer is: there is no published figure to anchor a boundary for it,
 * so a step would be invented twice over.
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
  // Absent for a Session measured before the seams were kept; the plot then
  // simply draws one continuous stretch of speaking time.
  const breaks = detail.turn_breaks as number[] | undefined;
  const step = detail.liveliness as string | undefined;
  const bandLow = detail.band_low_st as number | undefined;
  const bandHigh = detail.band_high_st as number | undefined;

  // A Session measured before the factors existed carries the range and
  // nothing else. Its recording is long gone (ADR 0048), so the rest cannot be
  // reconstructed; the block says so rather than showing empty rows.
  if (!curve || !median) {
    return (
      <p className="muted">
        Für dieses Training liegt nur der Umfang vor. Der Tonhöhenverlauf wurde damals noch nicht
        mitgeschrieben, und die Aufnahme ist gelöscht, wie bei jedem Gespräch.
      </p>
    );
  }

  return (
    <>
      <PitchContour
        curveHz={curve}
        medianHz={median}
        stepMs={stepMs}
        // The measured ends of the range where they exist. The fallback assumes
        // the band sits symmetrically around the median, which is what this
        // drawing did before the two ends were measured -- near enough on most
        // voices, wrong on any voice that reaches further one way than the
        // other, and kept only so a Session stored in between still draws.
        bandLowSt={bandLow ?? -measurement.value / 2}
        bandHighSt={bandHigh ?? measurement.value / 2}
        breaks={breaks}
      />

      <h3 className="factor-heading">Vier Größen aus diesem Verlauf</h3>
      <dl className="factor-list">
        <Factor
          name="Umfang"
          value={`${measurement.value.toFixed(1)} Halbtöne`}
          explanation={
            `Zwischen Ihrem tiefsten und höchsten üblichen Ton liegt das ` +
            `${Math.pow(2, measurement.value / 12).toFixed(2)}-fache der Frequenz. ` +
            `Das ist eine Spanne, keine Lage: Ihre mittlere Stimmlage liegt bei ` +
            `${Math.round(median)} Hz und geht in diese Zahl nicht ein. ` +
            rangeReading(step)
          }
        />

        {movement !== undefined && (
          <Factor
            name="Bewegung"
            value={`${movement.toFixed(1)} Halbtöne pro Sekunde`}
            explanation={
              "Zählt man alle Auf- und Abbewegungen zusammen, legt Ihre Stimme pro Sekunde " +
              `Sprechzeit rund ${movement.toFixed(0)} Halbtöne zurück. Es ist also eine ` +
              "Wegstrecke, keine Spanne. Zusammen mit dem Umfang trennt das zwei sehr " +
              "verschiedene Sprechweisen: Man kann eine weite Spanne erreichen, indem man " +
              "langsam von hoch nach tief driftet, und dieselbe Spanne, indem man in jedem " +
              "Satz arbeitet. Zu dieser Zahl gibt es bewusst keine Einordnung, denn anders als " +
              "beim Umfang gibt es keinen belegten Vergleichswert, an dem sie zu messen wäre."
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

/**
 * What the five-step reading means, in one sentence each.
 *
 * The step itself is decided in the backend and shown above with its scale;
 * this only says what it sounds like, and says it without an instruction. Two
 * of the five carry a caveat rather than advice: a very narrow span can be a
 * deliberate register, and a very wide one is as often a tracking error as a
 * performance.
 */
function rangeReading(step: string | undefined): string {
  switch (step) {
    case "very_monotone":
      return (
        "Auf der Skala oben ist das stark monoton: Ihre Stimme blieb fast auf einer Höhe. " +
        "Auf ein Gegenüber wirkt das schnell teilnahmslos, und Betonungen kommen kaum an. " +
        "Am Telefon fällt es stärker auf als im Raum, weil Mimik und Haltung wegfallen."
      );
    case "monotone":
      return (
        "Auf der Skala oben ist das monoton: die Melodie bewegt sich, aber wenig. Wenn Sie " +
        "beim Hören merken, dass eine wichtige Stelle nicht heraussticht, ist das hier die " +
        "Zahl dazu."
      );
    case "balanced":
      return (
        "Auf der Skala oben ist das ausgewogen: eine Spanne, wie sie in ruhigen Gesprächen " +
        "üblich ist."
      );
    case "lively":
      return (
        "Auf der Skala oben ist das lebendig: Ihre Stimme trägt hörbar mit, was Sie sagen."
      );
    case "exaggerated":
      return (
        "Auf der Skala oben liegt das über „lebendig“. Das kann sehr ausdrucksstarkes " +
        "Sprechen sein. Es kann auch ein Messfehler sein: Springt die Tonhöhenerkennung an " +
        "einer Stelle eine Oktave, wird die Spanne zu groß. Ein Blick auf den Verlauf zeigt, " +
        "was von beidem zutrifft."
      );
    default:
      return "";
  }
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
