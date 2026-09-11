import type { ReactNode } from "react";

import type { Measurement, TrafficLight } from "../protocol";
import InfoDetails from "./InfoDetails";
import PitchContour from "./PitchContour";

/**
 * What a speaker's pitch contour says about their delivery (F-35).
 *
 * The layout: the contour, one sentence with the coloured classification in it,
 * then the five figures as tiles in the same grid the Kennzahlen use. Each tile
 * carries its own "i" with what it measures and what it is worth. Below them
 * the one or two readings that mean something without a norm.
 *
 * The method used to sit in a paragraph under every figure, which put the one
 * sentence a reader acts on in the middle of six hundred words about
 * measurement. Nothing was deleted, only moved behind the icons.
 *
 * Where this is allowed to interpret, and where it is not:
 *
 * The Lebendigkeit carries the classification and the traffic light, and it is
 * the only figure here that carries either, because it is the only one with a
 * published boundary (Hincks 2005, measured against human liveliness ratings).
 * ADR 0078 holds the conditions that come with a light; ADR 0077 records why
 * the reading sits on this figure and not on the Umfang, whose old five-step
 * scale had nothing behind its derivation.
 *
 * The endings and the development need no norm at all: a slope rises or falls
 * regardless of whose voice it is, and a speaker compared with themselves has
 * no reference point to invent. The wording still stops at the observation and
 * leaves the question of whether it was intended to the person who was there.
 */

/** Below this a change between the first and last third is wobble, not a
 *  development worth a sentence. Three semitones is a minor third. */
const NOTABLE_CHANGE_ST = 3;

interface Endings {
  falling: number;
  rising: number;
  level: number;
}

export default function IntonationReading({
  measurement,
  toneFit = null,
}: {
  measurement: Measurement;
  /**
   * Whether the tone suited the occasion, from the wrap-up (`feedback.tone_fit`).
   *
   * It is rendered here and not in the wrap-up because it answers the question
   * the figures on this page raise and cannot settle: how much melody is
   * appropriate depends on the occasion, and every caveat in this block says
   * so. Null for a training whose wrap-up predates it, or one still being
   * written, in which case the block is left out rather than shown empty.
   */
  toneFit?: string | null;
}) {
  const detail = measurement.detail ?? {};
  const curve = detail.curve_hz as (number | null)[] | undefined;
  const median = detail.median_hz as number | undefined;
  const stepMs = (detail.curve_step_ms as number | undefined) ?? 100;
  // `null` and not just `undefined` throughout: these are Optional on the
  // Python side, so a figure the contour did not support arrives as JSON null
  // rather than as a missing key. `!== undefined` lets a null through, and
  // `(null * 100).toFixed(0)` is the string "0", so the screen would report a
  // measurement that was never taken.
  const movement = detail.movement_st_per_s as number | null | undefined;
  const endings = detail.endings as Endings | undefined;
  const first = detail.range_first_st as number | null | undefined;
  const last = detail.range_last_st as number | null | undefined;
  // Absent for a Session measured before the seams were kept; the plot then
  // simply draws one continuous stretch of speaking time.
  const breaks = detail.turn_breaks as number[] | undefined;
  const bandLow = detail.band_low_st as number | undefined;
  const bandHigh = detail.band_high_st as number | undefined;
  // Absent for a Session measured before the reading moved onto this figure
  // (ADR 0077). The step and the colour are then absent too, and the block says
  // so rather than reinstating the withdrawn scale from the Umfang.
  const pvq = detail.pvq as number | null | undefined;
  const pvqWindows = (detail.pvq_windows as number | null | undefined) ?? 0;
  const label = detail.liveliness_label as string | undefined;
  const light = detail.liveliness_light as TrafficLight | undefined;

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

  const notes = [endingsNote(endings), developmentNote(first, last)].filter(
    (note): note is string => note !== null,
  );

  return (
    <>
      <PitchContour
        curveHz={curve}
        medianHz={median}
        stepMs={stepMs}
        // The measured ends of the range where they exist. The fallback assumes
        // the band sits symmetrically around the median, which is what this
        // drawing did before the two ends were measured. Near enough on most
        // voices, wrong on any voice that reaches further one way than the
        // other, and kept only so a Session stored in between still draws.
        bandLowSt={bandLow ?? -measurement.value / 2}
        bandHighSt={bandHigh ?? measurement.value / 2}
        breaks={breaks}
      />

      <p className="melody-lead">{lead(pvq, label, light)}</p>

      {toneFit && (
        <section className="melody-fit">
          <h3>Passte der Ton zum Anlass?</h3>
          <p>{toneFit}</p>
          <p className="melody-fit-caveat">
            Diese Einordnung schreibt das Sprachmodell aus dem Gesprächsverlauf und der Situation,
            die Sie geübt haben. Sie ist eine Lesart, keine Messung, und sie kann daneben liegen.
            Die Zahlen darunter sind gemessen.
          </p>
        </section>
      )}

      <h3 className="melody-heading">Die Zahlen dahinter</h3>

      <div className="metric-grid melody-grid">
        {pvq != null && (
          <Tile
            name="Lebendigkeit"
            value={label ?? `${(pvq * 100).toFixed(0)} %`}
            light={light}
            subline={label ? `${(pvq * 100).toFixed(0)} % Schwankung` : "zu wenig Sprechzeit"}
            info="Was die Lebendigkeit misst"
          >
            <p>
              Wie stark Ihre Tonhöhe um Ihre eigene mittlere Stimmlage schwankt, angegeben als
              Prozent dieser Stimmlage. Gemessen jeweils über zehn Sekunden Sprechzeit und danach
              gemittelt.
              {pvqWindows > 0 && (
                <>
                  {" "}
                  Bei Ihnen kamen{" "}
                  {pvqWindows === 1 ? "zehn Sekunden" : `${pvqWindows} solche Abschnitte`}{" "}
                  zusammen.
                </>
              )}{" "}
              Abschnittsweise deshalb, weil sonst schon das langsame Absinken von einer Äußerung
              zur nächsten als Melodie zählen würde, obwohl die Stimme innerhalb der Sätze ruhig
              blieb.
            </p>
            <p>
              Diese Größe trägt als einzige hier eine Einstufung, weil es für sie Grenzwerte gibt,
              die gegen das Urteil echter Zuhörer geprüft wurden. Geprüft wurden sie allerdings an
              18 schwedischen Studierenden, die auf Englisch im Seminarraum präsentiert haben,
              nicht an deutschen Telefongesprächen. Nehmen Sie die Farbe als Hinweis, nicht als
              Befund.
            </p>
            <p>
              Die Farbe zeigt hin, sie benotet nicht. Grün heißt, dass hier heute nichts Ihre
              Aufmerksamkeit braucht, nicht „gut gemacht". Gelb heißt nachsehen, denn so hohe Werte
              entstehen auch durch Nervosität, Verhaspler oder einen Messfehler im Verlauf oben.
              Und wie viel Melodie passend ist, hängt vom Anlass ab: eine Reklamation klingt zu
              Recht anders als ein Verkaufsgespräch.
            </p>
          </Tile>
        )}

        <Tile
          name="Umfang"
          value={`${measurement.value.toFixed(1)} Halbtöne`}
          subline={`das ${Math.pow(2, measurement.value / 12).toFixed(2)}-fache der Frequenz`}
          info="Was der Umfang misst"
        >
          <p>
            Der Abstand zwischen Ihrem tiefsten und Ihrem höchsten üblichen Ton. Eine Spanne, keine
            Lage: Ihre mittlere Stimmlage von {Math.round(median)} Hz geht in die Zahl nicht ein.
          </p>
          <p>
            In Halbtönen und nicht in Hertz, damit eine tiefe und eine hohe Stimme bei gleicher
            Lebendigkeit dieselbe Zahl bekommen. Von den gebräuchlichen Tonhöhenskalen bildet diese
            die menschliche Wahrnehmung am besten ab.
          </p>
          <p>
            Eine Einstufung bekommt der Umfang bewusst nicht. Es gibt keinen belegten Wert dafür,
            ab wann eine Spanne eng oder weit ist, und eine Farbe darauf wäre eine erfundene Grenze.
          </p>
        </Tile>

        {movement != null && (
          <Tile
            name="Bewegung"
            value={`${movement.toFixed(0)} Halbtöne/s`}
            subline="pro Sekunde Sprechzeit"
            info="Was die Bewegung misst"
          >
            <p>
              Alle Auf und Ab Ihrer Stimme zusammengezählt: wie viele Halbtöne sie pro Sekunde
              Sprechzeit zurücklegt. Eine Wegstrecke, keine Spanne.
            </p>
            <p>
              Zusammen mit dem Umfang trennt das zwei sehr verschiedene Sprechweisen. Man kann eine
              weite Spanne erreichen, indem man langsam von hoch nach tief driftet, und dieselbe
              Spanne, indem man in jedem Satz arbeitet.
            </p>
            <p>
              Auch dazu gibt es keine Einstufung. Diese Zahl wäre der genauere Maßstab für
              Lebendigkeit als jede Spanne, aber es ist zu ihr kein Vergleichswert veröffentlicht.
            </p>
          </Tile>
        )}

        {endings && endings.falling + endings.rising + endings.level > 0 && (
          <Tile
            name="Satzenden"
            value={endingsValue(endings)}
            subline={endingsSubline(endings)}
            info="Wie die Satzenden gelesen werden"
          >
            <p>
              Gelesen aus den letzten 400 Millisekunden jeder Äußerung, und nur aus den Stellen, an
              denen Ihre Stimme wirklich klingt. Sätze enden oft in einem Konsonanten oder einem
              Atemzug, und die tragen keine Tonhöhe.
            </p>
            <p>
              Als Richtung zählt eine Bewegung erst ab 0,8 Halbtönen. Kleinere Bewegungen nimmt ein
              Zuhörer nicht mehr als Richtung wahr, sondern als gleichbleibenden Ton.
            </p>
            <p>
              Eine fallende Endung schließt eine Aussage ab, eine steigende lässt sie offen, fragt
              oder sucht Zustimmung. Keines von beidem ist für sich richtig oder falsch.
            </p>
          </Tile>
        )}

        {first != null && last != null && (
          <Tile
            name="Verlauf"
            value={`${first.toFixed(1)} → ${last.toFixed(1)}`}
            subline={developmentSubline(first, last)}
            info="Was der Verlauf vergleicht"
          >
            <p>
              Der Umfang im ersten Drittel gegen den im letzten. Verglichen werden Drittel Ihrer
              Sprechzeit und nicht der Uhr, eine Pause im Gespräch gehört also zu keinem von beiden.
            </p>
            <p>
              Das ist ein Vergleich von Ihnen mit Ihnen selbst. Er braucht keinen Vergleichswert
              von außen und ist deshalb die einzige Aussage hier, die ohne jede fremde Grenze
              auskommt.
            </p>
          </Tile>
        )}
      </div>

      {notes.length > 0 && (
        <ul className="melody-notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </>
  );
}

/**
 * One figure as a tile, in the same grid the Kennzahlen use.
 *
 * The shape is `.metric` deliberately, so these read as the same kind of thing
 * as the tiles in the wrap-up rather than as a second design. What they add is
 * the icon: on the wrap-up grid the explanation lives on the Kennzahl's own
 * page, and here there is no further page to go to.
 */
function Tile({
  name,
  value,
  subline,
  light,
  info,
  children,
}: {
  name: string;
  value: string;
  subline?: string;
  light?: TrafficLight | undefined;
  /** The accessible name of the icon. Hidden from the eye, because the same
   *  label on every tile of a grid is noise. */
  info: string;
  children: ReactNode;
}) {
  return (
    <div className="metric melody-tile">
      <span className="metric-name">{name}</span>
      <span className={`metric-value${light ? ` metric-value-${light}` : ""}`}>{value}</span>
      {subline && <span className="metric-subline">{subline}</span>}
      <InfoDetails label={info} iconOnly>
        {children}
      </InfoDetails>
    </div>
  );
}

/**
 * The one sentence this screen is built around.
 *
 * The classification in words, coloured, plus what it sounds like to somebody
 * on the other end of the line. Short: a reader who wants the rest opens an
 * icon, and a reader who stops here should still leave with the right
 * impression.
 */
function lead(
  pvq: number | null | undefined,
  label: string | undefined,
  light: TrafficLight | undefined,
): ReactNode {
  if (pvq == null) {
    return (
      "Für dieses Training haben wir die Lebendigkeit nicht gemessen. Sie kam später dazu, " +
      "und die Aufnahme ist gelöscht, wie bei jedem Gespräch. Der Verlauf oben und die " +
      "Zahlen darunter stimmen trotzdem."
    );
  }
  if (!label) {
    return (
      "Sie haben in diesem Gespräch zu wenig gesprochen, um Ihre Sprachmelodie einzuordnen. " +
      "Die Zahlen stehen, die Einstufung dazu wäre geraten."
    );
  }
  return (
    <>
      Ihre Sprachmelodie war{" "}
      <strong className={light ? `metric-value-${light}` : undefined}>{label}</strong>.{" "}
      {SOUNDS_LIKE[label] ?? ""}
    </>
  );
}

/** What each step sounds like to the person on the other end, in one sentence.
 *  Keyed by the German label, which the backend serves beside the threshold it
 *  came from, so a relabelling shows up here as a missing sentence rather than
 *  as a wrong one. */
const SOUNDS_LIKE: Record<string, string> = {
  monoton:
    "Ihre Stimme blieb fast auf einer Höhe. Am Telefon fällt das stärker auf als im Raum, " +
    "weil Mimik und Haltung wegfallen, und wichtige Stellen heben sich dann kaum ab.",
  lebendig: "Ihre Stimme trägt hörbar mit, was Sie sagen.",
  "sehr lebendig":
    "Das ist der Bereich der ausdrucksstärksten Sprecher. Gelb heißt hier nicht schlechter, " +
    "sondern nachsehen: So hohe Werte entstehen auch durch Nervosität, Verhaspler oder einen " +
    "Messfehler im Verlauf oben.",
};

function endingsValue({ falling, rising, level }: Endings): string {
  return `${falling} ↓ · ${rising} ↑ · ${level} →`;
}

function endingsSubline({ falling, rising, level }: Endings): string {
  return `${falling} fallend, ${rising} steigend, ${level} gleichbleibend`;
}

/**
 * What the endings say, in one sentence, or nothing.
 *
 * What is worth noticing is the mismatch between what somebody meant and how it
 * landed, and only the speaker can settle that, so the sentence stops at the
 * observation.
 */
function endingsNote(endings: Endings | undefined): string | null {
  if (!endings) return null;
  const { falling, rising, level } = endings;
  const total = falling + rising + level;
  if (total === 0) return null;

  if (rising > falling) {
    return (
      `Die meisten Ihrer Sätze endeten steigend (${rising} von ${total}). Das wirkt offen und ` +
      "einladend, bei sachlichen Aussagen aber auch unsicherer, als Sie es meinen."
    );
  }
  if (falling > rising) {
    return (
      `Die meisten Ihrer Sätze endeten fallend (${falling} von ${total}). Das wirkt ` +
      "abschließend und bestimmt. Wo Sie gefragt oder zum Weiterreden eingeladen haben, lohnt " +
      "der Blick, ob die Melodie das mitgetragen hat."
    );
  }
  return `Fallende und steigende Satzenden hielten sich die Waage (${falling} zu ${rising}).`;
}

function developmentSubline(first: number, last: number): string {
  const change = last - first;
  if (Math.abs(change) < NOTABLE_CHANGE_ST) return "erstes zu letztem Drittel";
  return change < 0
    ? `enger um ${Math.abs(change).toFixed(1)} Halbtöne`
    : `weiter um ${change.toFixed(1)} Halbtöne`;
}

/** A comparison of the speaker with themselves, which is the only comparison
 *  available here without a norm. Silent when nothing moved. */
function developmentNote(
  first: number | null | undefined,
  last: number | null | undefined,
): string | null {
  if (first == null || last == null) return null;
  const change = last - first;
  if (Math.abs(change) < NOTABLE_CHANGE_ST) return null;

  if (change < 0) {
    return (
      `Gegen Ende wurde Ihre Melodie enger, um ${Math.abs(change).toFixed(1)} Halbtöne. Das ` +
      "passiert oft, wenn ein Gespräch anstrengend wird oder zum Schluss nur noch Formalien " +
      "abgearbeitet werden."
    );
  }
  return `Gegen Ende wurde Ihre Melodie weiter, um ${change.toFixed(1)} Halbtöne.`;
}
