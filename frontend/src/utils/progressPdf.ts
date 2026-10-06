import type { FocusGoal, SessionSummary } from "../protocol";
import { showsInOverview } from "./metrics";
import { GROUPS, groupOf, type MetricGroup } from "./metricGroups";
import {
  focusOutline,
  recurringOutline,
  type FocusOutline,
  type FocusReading,
  type RecurringOutline,
} from "./progressOutline";
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
  completedOnly,
  formatBand,
  formatPoint,
  partsSummary,
  readable,
  selectionSeries,
  variety,
  type MetricSeries,
} from "./progressStats";
import { formatDate } from "./time";

/** The progress screen as a PDF (F-13). Never a report card: no target, colour,
 * arrow, difference or aggregate (ADR 0004/0051/0065), and it says so. */

const COURSE = { width: 42, height: 8 };
/** Fixed, so a page break never separates a name from its course. */
const ROW_HEIGHT = 11;
/** Column offsets from the left margin; the band text is fitted into what is left. */
const COLUMN = { value: 56, course: 86, band: 136 };
const COUNT_WIDTH = 17;
/** More than six-month retention can fill (ADR 0067). */
const MAX_MONTHS = 12;
/** Paper has no "show more" button; the rest is counted. */
const MAX_PAIRINGS = 12;

export interface ProgressPdfOptions {
  /** Every stored training: the record ignores the period switch, as on screen. */
  sessions: SessionSummary[];
  /** What every figure below the record is read over. */
  selected: SessionSummary[];
  phrase: string;
  catalogue: FocusGoal[];
  picked: string[];
  truncated?: boolean;
  date?: Date;
}

/** Without saving, like `buildFeedbackPdf`; no caller in the repo on purpose. */
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
  // The screen's own list, so the file cannot differ from the page.
  const series = selectionSeries(selected).filter((s) => showsInOverview(s.key));
  const long = readable(selected);

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

  // Before any figure: printed numbers about a person read as an assessment.
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
  // A sheet cannot be asked why a course rests on fewer calls.
  if (selected.length > long.length) {
    const short = selected.length - long.length;
    sheet.paragraph(
      `${short === 1 ? "Eines dieser Gespräche war" : `${short} dieser Gespräche waren`} zu ` +
        "kurz, um daraus Kennzahlen zu lesen. Die Kurven weiter unten sind deshalb über " +
        `${long.length} Trainings gezeichnet; gezählt ${short === 1 ? "ist es" : "sind sie"} ` +
        "oben mit.",
      { size: 9, colour: MUTED, lineHeight: 4.3 },
    );
    sheet.y += 4;
  }
  sheet.y += 4;

  record(sheet, sessions, counts);
  // Decided in `progressOutline`, like the screen (ADR 0102).
  focus(
    sheet,
    focusOutline({
      goals: catalogue.filter((goal) => picked.includes(goal.key)),
      series,
      selected,
      readable: long,
      shows: showsInOverview,
    }),
  );
  recurring(sheet, recurringOutline(selected, catalogue));
  metrics(sheet, series, long.length);

  return { doc: sheet.doc, filename: `Calltrainer_Fortschritt_${stamp(date)}.pdf` };
}

export async function downloadProgressPdf(options: ProgressPdfOptions): Promise<void> {
  const { doc, filename } = await buildProgressPdf(options);
  doc.save(filename);
}

/** The calendar as trainings per month; the variety table as pairings with counts. */
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

/** A goal without a measurement says so, rather than seeming tracked. */
function focus(sheet: Sheet, outline: FocusOutline[]) {
  if (outline.length === 0) return;

  sheet.heading("Woran Sie arbeiten", "Ihre Fokusziele");

  for (const entry of outline) {
    sheet.keep(14);
    sheet.paragraph(entry.title, { size: 10.5, style: "bold", colour: NAVY });
    sheet.paragraph(goalSentence(entry.reading), { size: 9, colour: MUTED, lineHeight: 4.3 });
    sheet.y += 3;
  }
  sheet.y += 4;
}

/** The state is decided in `progressOutline` (ADR 0102); only the wording is this file's. */
function goalSentence(reading: FocusReading): string {
  switch (reading.kind) {
    case "metric": {
      const { series, last, band, trainings } = reading;
      return (
        `${series.name}: zuletzt ${last ?? "kein Wert"}` +
        (band ? `, üblicher Bereich ${band}` : "") +
        `, aus ${trainings} Trainings.`
      );
    }
    case "no-value":
      return reading.note;
    case "segment":
      return (
        "Verglichen werden hier zwei Abschnitte eines Gesprächs; der Vergleich steht in " +
        "der Auswertung des jeweiligen Trainings."
      );
    case "activity":
      return "Was dieses Ziel beantwortet, steht oben unter „Ihr Training“.";
    case "mentions": {
      const { improvements, strengths, total, note, measured } = reading;
      // Only the halves that happened: "in 0 als Stärke" reads as a score (ADR 0080).
      const named = [
        ...(improvements > 0 ? [`in ${improvements} als Verbesserung`] : []),
        ...(strengths > 0 ? [`in ${strengths} als Stärke`] : []),
      ];
      if (total === 0 || named.length === 0) return note;
      const lead = measured ? "Noch kein Messwert in dieser Auswahl." : "Keine Messung.";
      return `${lead} Von ${total} ausgewerteten Trainings ${named.join(", ")} genannt.`;
    }
  }
}

/** Statements over a named denominator, never a percentage (ADR 0080). */
function recurring(sheet: Sheet, summary: RecurringOutline) {
  if (summary.total === 0) return;
  if (summary.strengths.length === 0 && summary.improvements.length === 0) return;

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
      // A retired goal (ADR 0076) shows its key.
      sheet.doc.text(drawable(entry.title ?? entry.goal), MARGIN.left, sheet.y);
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

      // A checklist's sentence takes the course column too.
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

/** Shrunk rather than clipped: half a sentence says something else. */
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

/** As `Sparkline.tsx` draws it: one ink colour, no direction mark. */
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

  // The latest value, matching the figure printed beside it.
  doc.setFillColor(...BLUE);
  doc.circle(px(values.length - 1), py(values[values.length - 1]!), 0.7, "F");
}

/** Completed only, as the calendar counts them. */
function byMonth(sessions: SessionSummary[]): [string, number][] {
  const counts = new Map<string, { label: string; count: number; at: number }>();
  for (const session of completedOnly(sessions)) {
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
