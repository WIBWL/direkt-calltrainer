import type { ReactNode } from "react";

import type { Measurement, TrafficLight } from "../protocol";
import { formatNumber } from "../utils/metrics";
import InfoDetails from "./InfoDetails";
import PitchContour from "./PitchContour";

/** The pitch contour's reading (F-35). Only liveliness carries a class and light
 * (ADR 0077/0078); endings and development need no norm. */

/** Below a minor third, a change between thirds is wobble. */
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
  /** From the wrap-up (ADR 0079); null leaves the block out. */
  toneFit?: string | null;
}) {
  const detail = measurement.detail ?? {};
  const curve = detail.curve_hz as (number | null)[] | undefined;
  const median = detail.median_hz as number | undefined;
  const stepMs = (detail.curve_step_ms as number | undefined) ?? 100;
  // `null` too: Optional fields arrive as JSON null, and `(null * 100).toFixed(0)` is "0".
  const movement = detail.movement_st_per_s as number | null | undefined;
  const endings = detail.endings as Endings | undefined;
  const first = detail.range_first_st as number | null | undefined;
  const last = detail.range_last_st as number | null | undefined;
  const breaks = detail.turn_breaks as number[] | undefined;
  const bandLow = detail.band_low_st as number | undefined;
  const bandHigh = detail.band_high_st as number | undefined;
  // Null with too little voiced speech: no step, no colour.
  const pvq = detail.pvq as number | null | undefined;
  const pvqWindows = (detail.pvq_windows as number | null | undefined) ?? 0;
  const label = detail.liveliness_label as string | undefined;
  const light = detail.liveliness_light as TrafficLight | undefined;

  if (!curve || !median) return null;

  const notes = [endingsNote(endings), developmentNote(first, last)].filter(
    (note): note is string => note !== null,
  );

  return (
    <>
      <PitchContour
        curveHz={curve}
        medianHz={median}
        stepMs={stepMs}
        bandLowSt={bandLow}
        bandHighSt={bandHigh}
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
          value={`${formatNumber(measurement.value, 1)} Halbtöne`}
          subline={`das ${formatNumber(Math.pow(2, measurement.value / 12), 2)}-fache der Frequenz`}
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
            value={`${formatNumber(first, 1)} → ${formatNumber(last, 1)}`}
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

/** Shaped as `.metric`, plus an "i", since there is no further page. */
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
  /** Hidden from the eye: the same label on every tile is noise. */
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

/** Keyed by the backend's label, so a relabelling shows as a missing sentence, not a wrong one. */
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

/** Stops at the observation: only the speaker knows whether it landed as meant. */
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
    ? `enger um ${formatNumber(Math.abs(change), 1)} Halbtöne`
    : `weiter um ${formatNumber(change, 1)} Halbtöne`;
}

/** The speaker against themselves, the only comparison without a norm. */
function developmentNote(
  first: number | null | undefined,
  last: number | null | undefined,
): string | null {
  if (first == null || last == null) return null;
  const change = last - first;
  if (Math.abs(change) < NOTABLE_CHANGE_ST) return null;

  if (change < 0) {
    return (
      `Gegen Ende wurde Ihre Melodie enger, um ${formatNumber(Math.abs(change), 1)} Halbtöne. Das ` +
      "passiert oft, wenn ein Gespräch anstrengend wird oder zum Schluss nur noch Formalien " +
      "abgearbeitet werden."
    );
  }
  return `Gegen Ende wurde Ihre Melodie weiter, um ${formatNumber(change, 1)} Halbtöne.`;
}
