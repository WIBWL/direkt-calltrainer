import type { FocusGoal, SessionSummary } from "../protocol";
import { backingOf } from "./focusMetrics";
import { mentionSummary } from "./goalMentions";
import { showsInOverview } from "./metrics";
import { GROUPS, groupOf, type MetricGroup } from "./metricGroups";
import {
  BLUE,
  HEADING_HEIGHT,
  MARGIN,
  MUTED,
  NAVY,
  PAGE,
  RULE,
  drawable,
  openSheet,
  stamp,
  type Sheet,
} from "./pdfDocument";
import {
  MIN_SESSIONS_FOR_SERIES,
  activity,
  formatBand,
  formatPoint,
  partsSummary,
  selectionSeries,
  variety,
  type MetricSeries,
} from "./progressStats";
import { formatDate } from "./time";

/**
 * The progress screen as a PDF (F-13), the counterpart of the feedback file
 * F-64 offers after one call.
 *
 * Why it exists: the dashboard is what somebody takes into a conversation with
 * a trainer, an instructor or a supervisor, and the only way to take it was a
 * screenshot per block. It carries what the page carries, in the page's own
 * order — the record of what was trained, the focus goals, what the wrap-ups
 * keep naming, and every metric over time — read over the trainings the page's
 * switches select, which the first page states in words.
 *
 * What it must not become, and what the page may not either: a report card.
 * No target, no colour meaning good or bad, no arrow, no difference between an
 * earlier figure and a later one, no aggregate (ADR 0004, ADR 0051, ADR 0065).
 * The rule bites harder on paper than on screen: a sheet handed to somebody
 * else is read as an assessment of the person unless it says otherwise, so it
 * says otherwise twice, once under the title and once at the foot.
 *
 * Built in the browser, from the numbers the page already holds. A server route
 * would be a second path to the same figures, which is the one thing
 * `docs/dashboard-konzept.md` section 9 rules out by name; jsPDF and the fonts
 * are fetched on the press, exactly as the feedback file's are.
 *
 * The page chrome is shared with that file (`pdfDocument.ts`), so the two
 * documents look like one application.
 */

/** One course beside a metric's figures, in millimetres. Small on purpose: it
 *  is the shape of the row, and the figures beside it are the reading. */
const COURSE = { width: 42, height: 8 };
/** One row of the metric list. Fixed, so a page break never lands between a
 *  name and the course belonging to it. */
const ROW_HEIGHT = 11;
/** Where the columns of that list sit, measured from the left margin, and how
 *  much room the count at the right-hand end takes. The band text is fitted
 *  into what is left: "128 bis 138 WPM" beside a right-aligned "9 von 9" ran
 *  into it at the first long unit. */
const COLUMN = { value: 56, course: 86, band: 136 };
const COUNT_WIDTH = 17;
/** At most this many months under the training record. Twelve is already more
 *  than the six-month retention can fill (ADR 0067); the cap is there so an
 *  account that somehow holds more does not print a page of them. */
const MAX_MONTHS = 12;
/** At most this many rows of the variety list. The grid on screen collapses
 *  after five and offers the rest behind a button; paper has no button, so it
 *  prints the ones that carry the training and says how many it left out. */
const MAX_PAIRINGS = 12;

export interface ProgressPdfOptions {
  /** Every stored training, newest first — what the record at the top counts,
   *  exactly as on screen, where the period switch deliberately does not reach
   *  that block. */
  sessions: SessionSummary[];
  /** The trainings the switches select: what every figure below the record is
   *  read over. */
  selected: SessionSummary[];
  /** That selection in words ("Ihren letzten 5 Beratungsgesprächen"), from the
   *  same place the pages without a switch take it (`ProgressContext`). */
  phrase: string;
  /** The focus catalogue, for turning a key into its German title. */
  catalogue: FocusGoal[];
  /** The goals the user picked, by key. */
  picked: string[];
  /** Whether the account holds more trainings than the dashboard read. */
  truncated?: boolean;
  date?: Date;
}

/** The document and the name to save it under, without saving it — separate
 *  from the download so the layout can be built and looked at outside a
 *  browser, the way the feedback file's is. */
export async function buildProgressPdf({
  sessions,
  selected,
  phrase,
  catalogue,
  picked,
  truncated = false,
  date = new Date(),
}: ProgressPdfOptions) {
  const sheet = await openSheet("Ihr Fortschritt");

  const counts = activity(sessions);
  // The same list the screen reads (`selectionSeries`), so the file cannot
  // show a row the page does not, or miss one it does.
  const series = selectionSeries(selected).filter((s) => showsInOverview(s.key));

  sheet.facts([
    ["Ausgewertet", `${selected.length} von ${sessions.length}`],
    ["Auswahl", phrase],
    ...(counts.firstAt && counts.lastAt
      ? ([
          ["Zeitraum", `${formatDate(counts.firstAt)} bis ${formatDate(counts.lastAt)}`],
        ] as [string, string][])
      : []),
    ["Erstellt", formatDate(date.toISOString()) ?? ""],
  ]);
  sheet.y += 3;

  // The sentence that has to be read before any figure on the sheet, and the
  // reason it has to: a printed page of numbers about a person is taken for an
  // assessment of them unless it says it is not.
  sheet.paragraph(
    "Diese Übersicht beschreibt Ihre eigenen Trainings. Bewertet wird nichts: Für keine " +
      "dieser Größen gibt es einen belegten Richtwert, an dem sie für Ihre Gespräche zu " +
      "messen wäre. Deshalb stehen hier Ihre Werte und der Bereich, in dem sie meistens " +
      "liegen, aber keine Zielwerte und kein Vergleich mit anderen.",
    { size: 9, colour: MUTED, lineHeight: 4.3 },
  );
  sheet.y += 4;
  if (truncated) {
    sheet.paragraph(
      `Gelesen wurden Ihre ${sessions.length} neuesten Trainings; Ihr Konto hält weitere.`,
      { size: 9, colour: MUTED, lineHeight: 4.3 },
    );
    sheet.y += 4;
  }
  sheet.y += 4;

  record(sheet, sessions, counts);
  focus(sheet, selected, catalogue, picked, series);
  recurring(sheet, selected, catalogue);
  metrics(sheet, series, selected.length);

  return { doc: sheet.doc, filename: `Calltrainer_Fortschritt_${stamp(date)}.pdf` };
}

export async function downloadProgressPdf(options: ProgressPdfOptions): Promise<void> {
  const { doc, filename } = await buildProgressPdf(options);
  doc.save(filename);
}

/**
 * What was trained, over every stored training.
 *
 * The calendar itself does not travel: a month grid is a shape for scanning,
 * and twelve of them would be four pages of squares. What a reader takes from
 * it — how many trainings fell in which month — is a list, and a list is what a
 * sheet of paper is good at. The variety table does travel, as pairings with
 * their counts, because on screen it is already a list.
 */
function record(
  sheet: Sheet,
  sessions: SessionSummary[],
  counts: ReturnType<typeof activity>,
) {
  sheet.heading("Was Sie getan haben", "Ihr Training");

  sheet.facts([
    ["Trainings", String(counts.sessions)],
    ["Szenarien", String(counts.scenarios)],
    ["Partner", String(counts.personas)],
  ]);
  sheet.y += 3;

  const months = byMonth(sessions);
  if (months.length > 0) {
    sheet.keep(8 + months.slice(0, MAX_MONTHS).length * 5);
    sheet.paragraph("Wann Sie trainiert haben", { size: 10, style: "bold", colour: NAVY });
    sheet.y += 1;
    for (const [label, count] of months.slice(0, MAX_MONTHS)) {
      sheet.keep(5);
      sheet.doc.setFont("app", "normal");
      sheet.doc.setFontSize(9);
      sheet.doc.setTextColor(...MUTED);
      sheet.doc.text(drawable(label), MARGIN.left, sheet.y);
      sheet.doc.setTextColor(...NAVY);
      sheet.doc.text(
        `${count} ${count === 1 ? "Training" : "Trainings"}`,
        MARGIN.left + 50,
        sheet.y,
      );
      sheet.y += 5;
    }
    sheet.y += 4;
  }

  const pairings = variety(sessions)
    .cells.slice()
    .sort((a, b) => b.count - a.count || a.scenario.localeCompare(b.scenario, "de"));
  if (pairings.length > 0) {
    sheet.keep(8 + Math.min(pairings.length, MAX_PAIRINGS) * 5);
    sheet.paragraph("Womit Sie trainiert haben", { size: 10, style: "bold", colour: NAVY });
    sheet.y += 1;
    for (const cell of pairings.slice(0, MAX_PAIRINGS)) {
      sheet.keep(5);
      sheet.doc.setFont("app", "normal");
      sheet.doc.setFontSize(9);
      sheet.doc.setTextColor(...NAVY);
      sheet.doc.text(drawable(`${cell.scenario} · ${cell.persona}`), MARGIN.left, sheet.y);
      sheet.doc.setTextColor(...MUTED);
      sheet.doc.text(`${cell.count}x`, PAGE.width - MARGIN.right, sheet.y, { align: "right" });
      sheet.y += 5;
    }
    if (pairings.length > MAX_PAIRINGS) {
      sheet.paragraph(`Und ${pairings.length - MAX_PAIRINGS} weitere Kombinationen.`, {
        size: 8.5,
        colour: MUTED,
        lineHeight: 4.2,
      });
    }
    sheet.y += 7;
  }
}

/** The picked focus goals, each with whatever honestly answers it — the four
 *  shapes the tiles take (`utils/focusMetrics.ts`), written out as lines. A
 *  goal with no measurement says so rather than being left off: a sheet that
 *  quietly dropped it would let the reader believe it is being tracked. */
function focus(
  sheet: Sheet,
  selected: SessionSummary[],
  catalogue: FocusGoal[],
  picked: string[],
  series: MetricSeries[],
) {
  const goals = catalogue.filter((goal) => picked.includes(goal.key));
  if (goals.length === 0) return;

  sheet.heading("Woran Sie arbeiten", "Ihre Fokusziele");

  for (const goal of goals) {
    sheet.keep(14);
    sheet.paragraph(goal.title, { size: 10.5, style: "bold", colour: NAVY });

    const backing = backingOf(goal.key);
    const primary = series.find((s) => s.key === backing.metrics[0]);
    if (backing.kind === "metric" && primary) {
      const last = primary.points[primary.points.length - 1];
      const band = formatBand(primary);
      sheet.paragraph(
        `${primary.name}: zuletzt ${last ? formatPoint(primary, last.value) : "kein Wert"}` +
          (band ? `, üblicher Bereich ${band}` : "") +
          `, aus ${primary.points.length} Trainings.`,
        { size: 9, colour: MUTED, lineHeight: 4.3 },
      );
    } else if (backing.kind === "metric") {
      // A goal that *has* a measurement, in a selection where nothing carries
      // it: a metric younger than these calls, or one the recordings could not
      // yield (ADR 0085). Said in so many words rather than falling through to
      // one of the sentences below, which would tell the reader this goal has
      // no measurement at all.
      sheet.paragraph(
        "In den ausgewerteten Trainings liegt dazu noch kein Messwert vor.",
        { size: 9, colour: MUTED, lineHeight: 4.3 },
      );
    } else if (backing.kind === "text") {
      const { improvements, strengths, total } = countMentions(selected, goal.key);
      // Only the halves that happened. "in 0 als Stärke" reads as a score of
      // zero, which is the one thing a count of statements must not become
      // (ADR 0080).
      const named = [
        ...(improvements > 0 ? [`in ${improvements} als Verbesserung`] : []),
        ...(strengths > 0 ? [`in ${strengths} als Stärke`] : []),
      ];
      sheet.paragraph(
        total === 0 || named.length === 0
          ? (backing.note ?? "Zu diesem Ziel liegt noch nichts vor.")
          : `Keine Messung. Von ${total} ausgewerteten Trainings ${named.join(", ")} genannt.`,
        { size: 9, colour: MUTED, lineHeight: 4.3 },
      );
    } else {
      sheet.paragraph(
        backing.kind === "segment"
          ? "Verglichen werden hier zwei Abschnitte eines Gesprächs; der Vergleich steht in " +
            "der Auswertung des jeweiligen Trainings."
          : "Was dieses Ziel beantwortet, steht oben unter „Ihr Training“.",
        { size: 9, colour: MUTED, lineHeight: 4.3 },
      );
    }
    sheet.y += 3;
  }
  sheet.y += 4;
}

/** What the wrap-ups keep naming. A frequency of statements over a named
 *  denominator, never a measurement and never a percentage — ADR 0080's
 *  wording kept word for word, because this is the block most easily misread as
 *  a grade and a sheet of paper cannot be asked a follow-up question. */
function recurring(sheet: Sheet, selected: SessionSummary[], catalogue: FocusGoal[]) {
  const summary = mentionSummary(selected);
  if (summary.total === 0) return;
  if (summary.strengths.length === 0 && summary.improvements.length === 0) return;

  const title = (key: string) => catalogue.find((goal) => goal.key === key)?.title ?? key;

  sheet.heading("Was wiederkehrt", "Aus Ihren Auswertungen");
  sheet.paragraph(
    `Gezählt wird, in wie vielen Ihrer ${summary.total} ausgewerteten Trainings ein Thema ` +
      "genannt wurde. Das ist eine Häufigkeit von Aussagen und keine Messung.",
    { size: 9, colour: MUTED, lineHeight: 4.3 },
  );
  sheet.y += 4;

  for (const [label, entries] of [
    ["Als Verbesserung genannt", summary.improvements],
    ["Als Stärke genannt", summary.strengths],
  ] as const) {
    if (entries.length === 0) continue;
    sheet.keep(8 + entries.length * 5);
    sheet.paragraph(label, { size: 10, style: "bold", colour: NAVY });
    sheet.y += 1;
    for (const entry of entries) {
      sheet.keep(5);
      sheet.doc.setFont("app", "normal");
      sheet.doc.setFontSize(9);
      sheet.doc.setTextColor(...NAVY);
      sheet.doc.text(drawable(title(entry.goal)), MARGIN.left, sheet.y);
      sheet.doc.setTextColor(...MUTED);
      sheet.doc.text(
        `in ${entry.count} von ${summary.total}`,
        PAGE.width - MARGIN.right,
        sheet.y,
        { align: "right" },
      );
      sheet.y += 5;
    }
    sheet.y += 3;
  }
  sheet.y += 4;
}

/**
 * Every metric over the selection, one row each, in the two families the
 * screen groups them under.
 *
 * The same list in the same order, with the course drawn beside the figures
 * rather than dropped: the shape of a series is half the reading, and a sheet
 * with the numbers and no shape would be the accessible half of the screen
 * instead of the screen.
 */
function metrics(sheet: Sheet, series: MetricSeries[], trainings: number) {
  if (series.length === 0) return;

  sheet.keep(HEADING_HEIGHT + ROW_HEIGHT * 3);
  sheet.heading("Wie Sie gesprochen haben", "Kennzahlen über die Zeit");

  for (const group of ["speech", "content"] as MetricGroup[]) {
    const rows = series.filter((s) => groupOf(s.aspect) === group);
    if (rows.length === 0) continue;

    sheet.keep(10 + ROW_HEIGHT * 2);
    sheet.paragraph(GROUPS[group].label, { size: 10, style: "bold", colour: NAVY });
    sheet.y += 1;

    for (const row of rows) {
      sheet.keep(ROW_HEIGHT);
      const top = sheet.y;
      const last = row.points[row.points.length - 1];

      sheet.doc.setFont("app", "normal");
      sheet.doc.setFontSize(9);
      sheet.doc.setTextColor(...NAVY);
      sheet.doc.text(drawable(row.name), MARGIN.left, top);

      sheet.doc.setFont("app", "bold");
      sheet.doc.text(
        drawable(last ? formatPoint(row, last.value) : "–"),
        MARGIN.left + COLUMN.value,
        top,
      );

      // A checklist has no usual range and no course (see `SeriesShape`): what
      // it says instead is how often every part was there, the same sentence
      // the table on screen puts in its range column. It is given the course
      // column as well, which is empty for such a row and which the sentence
      // needs — squeezed into the range column alone it came out at six point
      // and still ran into the count.
      if (row.shape === "parts") {
        fitted(sheet, partsSummary(row) ?? "–", MARGIN.left + COLUMN.course, top);
      } else {
        if (row.points.length >= MIN_SESSIONS_FOR_SERIES) {
          course(sheet, row, MARGIN.left + COLUMN.course, top - COURSE.height + 2);
        }
        fitted(sheet, formatBand(row) ?? "–", MARGIN.left + COLUMN.band, top);
      }

      sheet.doc.setFont("app", "normal");
      sheet.doc.setFontSize(8);
      sheet.doc.setTextColor(...MUTED);
      sheet.doc.text(
        `${row.points.length} von ${trainings}`,
        PAGE.width - MARGIN.right,
        top,
        { align: "right" },
      );

      sheet.y = top + ROW_HEIGHT;
    }
    sheet.y += 4;
  }

  sheet.keep(20);
  sheet.paragraph(
    "Der übliche Bereich ist der Median Ihrer Werte, erweitert um ihre typische Abweichung. " +
      "Er beschreibt, wo Ihre Werte meistens liegen, und ist kein Ziel: Ein Wert außerhalb " +
      "ist weder besser noch schlechter, nur seltener. „N von M“ sagt, aus wie vielen der " +
      "ausgewerteten Trainings eine Zeile besteht — eine Kennzahl kann jünger sein als ein " +
      "Gespräch, und eine zu verrauschte Aufnahme lässt mehrere zugleich ausfallen. Die " +
      "Lautstärke fehlt mit Absicht: Ihr Pegel hängt an Mikrofon und Abstand und ist über " +
      "Gespräche hinweg nicht vergleichbar.",
    { size: 8.5, colour: MUTED, lineHeight: 4.2 },
  );
}

/** One cell of the band column, set one step smaller where it would otherwise
 *  run into the count at the right-hand end. Shrinking rather than clipping:
 *  "In 5 von 9 Trainings alle 3 Teile erkannt" is a sentence, and half of one
 *  says something different from the whole. */
function fitted(sheet: Sheet, text: string, left: number, top: number) {
  const { doc } = sheet;
  const room = PAGE.width - MARGIN.right - COUNT_WIDTH - left;
  doc.setFont("app", "normal");
  for (const size of [8, 7, 6.2]) {
    doc.setFontSize(size);
    if (doc.getTextWidth(drawable(text)) <= room || size === 6.2) break;
  }
  doc.setTextColor(...MUTED);
  doc.text(drawable(text), left, top);
}

/** One metric's course, drawn the way `Sparkline.tsx` draws it: the user's own
 *  usual range behind it and the line over it, one ink colour, no mark for a
 *  direction. Colour here is the family's identity on screen and never a
 *  reading of a value, so on paper one colour loses nothing. */
function course(sheet: Sheet, series: MetricSeries, left: number, top: number) {
  const { doc } = sheet;
  const values = series.points.map((point) => point.value);
  const lowest = Math.min(...values, series.band?.low ?? Infinity);
  const highest = Math.max(...values, series.band?.high ?? -Infinity);
  const range = highest - lowest || Math.abs(highest) || 1;
  const last = Math.max(1, values.length - 1);

  const px = (index: number) => left + (index / last) * COURSE.width;
  const py = (value: number) =>
    top + COURSE.height - ((value - lowest) / range) * COURSE.height;

  if (series.band) {
    // Clamped: on an even series the band is wider than the values' own range.
    const bandTop = Math.max(top, py(series.band.high));
    const bandBottom = Math.min(top + COURSE.height, py(series.band.low));
    doc.setFillColor(...RULE);
    doc.rect(left, bandTop, COURSE.width, Math.max(0.3, bandBottom - bandTop), "F");
  }

  doc.setDrawColor(...BLUE);
  doc.setLineWidth(0.35);
  for (let i = 1; i < values.length; i += 1) {
    doc.line(px(i - 1), py(values[i - 1]!), px(i), py(values[i]!));
  }

  // The most recent value, which is the figure printed to the left of the
  // course, so the mark and the number agree.
  doc.setFillColor(...BLUE);
  doc.circle(px(values.length - 1), py(values[values.length - 1]!), 0.7, "F");
}

/** How often one goal was named in the selection, as a strength and as an
 *  improvement, counted per training the way the screen counts it: the same
 *  goal named twice in one wrap-up counts once. */
function countMentions(sessions: SessionSummary[], goal: string) {
  let strengths = 0;
  let improvements = 0;
  let total = 0;
  for (const session of sessions) {
    if (session.feedback_goals.length === 0) continue;
    total += 1;
    const kinds = new Set(
      session.feedback_goals.filter((tag) => tag.goal === goal).map((tag) => tag.kind),
    );
    if (kinds.has("strength")) strengths += 1;
    if (kinds.has("improvement")) improvements += 1;
  }
  return { strengths, improvements, total };
}

/** The trainings per calendar month, newest month first. Completed only, the
 *  way the calendar counts them: an abandoned call is not an answer to "when
 *  did I train" (ADR 0034's amendment). */
function byMonth(sessions: SessionSummary[]): [string, number][] {
  const counts = new Map<string, { label: string; count: number; at: number }>();
  for (const session of sessions) {
    if (session.status !== "completed") continue;
    const date = new Date(session.started_at);
    if (Number.isNaN(date.getTime())) continue;
    const key = `${date.getFullYear()}-${date.getMonth()}`;
    const entry = counts.get(key) ?? {
      label: date.toLocaleDateString("de-DE", { month: "long", year: "numeric" }),
      count: 0,
      at: date.getFullYear() * 12 + date.getMonth(),
    };
    entry.count += 1;
    counts.set(key, entry);
  }
  return [...counts.values()]
    .sort((a, b) => b.at - a.at)
    .map((entry) => [entry.label, entry.count]);
}
