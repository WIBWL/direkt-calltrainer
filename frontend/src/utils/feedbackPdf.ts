import type { FocusGoal, SessionDetail, TranscriptEntry } from "../protocol";
import {
  loudnessCourse,
  loudnessClock,
  loudnessRuns,
  LOUDNESS_CAPTION,
  type LoudnessCurve,
} from "./loudness";
import {
  BLUE,
  CAUTION,
  CONTENT_WIDTH,
  HEADING_HEIGHT,
  INK,
  LINE_HEIGHT,
  MARGIN,
  MUTED,
  NAVY,
  PAGE,
  RULE,
  SUCCESS,
  TRACKING,
  drawable,
  openSheet,
  stamp,
} from "./pdfDocument";
import { formatMetricValue, METRIC_DISCLAIMER, metricParts, metricSubline } from "./metrics";
import { reportOutline, type OutlinePoint } from "./reportOutline";
import { formatLongDate, formatOffset } from "./time";

/** The feedback page as a PDF (F-64). In the browser: an unconsented run is never
 * stored (ADR 0066), so this may be the only copy. Content from `reportOutline.ts`. */

/** Shared with cited feedback points, so their timestamps line up with the transcript's. */
const TEXT_INDENT = 17;

/** Fixed, so a tile with a second line does not lift its neighbour. */
const TILE = { columns: 2, height: 16 };
const PLOT_HEIGHT = 26;
/** The curve is smoothed over a second; more segments add nothing visible. */
const PLOT_SEGMENTS = 240;

export interface FeedbackPdfOptions {
  transcript: TranscriptEntry[];
  personaName: string;
  /** Named first: which conversation this was is what a reader needs first. */
  // `| undefined` because of `exactOptionalPropertyTypes`.
  scenarioName?: string | null | undefined;
  /** Absent for an unstored call (ADR 0066); its wrap-up may be missing too. */
  detail?: SessionDetail | null | undefined;
  goals?: FocusGoal[] | undefined;
  date?: Date;
}

/** Without saving, so the layout can be rendered outside a browser; no caller in the repo on purpose. */
export async function buildFeedbackPdf({
  transcript,
  personaName,
  scenarioName,
  detail,
  goals,
  date = new Date(),
}: FeedbackPdfOptions) {
  const outline = reportOutline({
    personaName,
    scenarioName,
    reverse: detail?.reverse,
    feedback: detail?.feedback,
    measurements: detail?.measurements,
    turns: detail?.turns,
    goals,
  });
  const { meta, wrapUp } = outline;
  // Without a wrap-up it is only a protocol.
  const title = wrapUp ? "Gesprächsfeedback" : "Gesprächsprotokoll";
  const sheet = await openSheet(title);
  const { doc } = sheet;

  const facts: [string, string][] = [
    ...(meta.scenario ? ([["Szenario", meta.scenario]] as [string, string][]) : []),
    ["Gesprächspartner", meta.partner],
    // The transcript reads the other way round in a reverse (ADR 0070).
    ...(meta.reversal ? ([["Rollentausch", meta.reversal]] as [string, string][]) : []),
    ["Datum", formatLongDate(date.toISOString()) ?? ""],
    ["Beiträge", String(transcript.length)],
  ];
  sheet.facts(facts);
  sheet.y += 7;

  if (wrapUp) {
    sheet.heading("Qualitative Einordnung", "Zusammenfassung");
    sheet.paragraph(wrapUp.summary);
    sheet.y += 9;

    points("Stärken", "Das gelang gut", wrapUp.strengths, SUCCESS);
    points("Weiterentwickeln", "Das können Sie verbessern", wrapUp.improvements, CAUTION);

    if (wrapUp.phaseLanguage) {
      sheet.heading("Gesprächsführung", "Phasengerechte Sprache");
      sheet.paragraph(wrapUp.phaseLanguage);
      sheet.y += 2.5;
      sheet.paragraph("Warm einsteigen, sachlich am Anliegen arbeiten, warm abschließen.", {
        size: 9,
        colour: MUTED,
        lineHeight: 4.4,
      });
      sheet.y += 9;
    }
  }

  metrics();
  protocol();

  /** Cited timestamps on the transcript's two columns; the goal as a small line over the point. */
  function points(
    eyebrow: string,
    name: string,
    list: OutlinePoint[],
    tone: [number, number, number],
  ) {
    if (list.length === 0) return;

    sheet.heading(eyebrow, name);
    for (const point of list) {
      sheet.keep(LINE_HEIGHT * (point.goal ? 3 : 2));
      if (point.offsetMs !== null) {
        doc.setFont("app", "normal");
        doc.setFontSize(8);
        doc.setTextColor(...MUTED);
        doc.text(formatOffset(point.offsetMs), MARGIN.left, sheet.y);
      }
      const top = sheet.y;
      if (point.goal) {
        sheet.paragraph(point.goal.toUpperCase(), {
          indent: TEXT_INDENT,
          size: 7,
          colour: MUTED,
          lineHeight: 4,
        });
      }
      sheet.paragraph(point.text, { indent: TEXT_INDENT });
      // The accent bar tells the two lists apart in print.
      doc.setDrawColor(...tone);
      doc.setLineWidth(0.8);
      if (sheet.y > top) doc.line(MARGIN.left + 13, top - 3.4, MARGIN.left + 13, sheet.y - 3.4);
      sheet.y += 3.5;
    }
    sheet.y += 6;
  }

  /** Both halves printed, since paper has no slider. Never a judgement (ADR 0004/0051). */
  function metrics() {
    const all = outline.metricGroups.flatMap((group) => group.measurements);
    if (all.length === 0) return;

    // Heading plus the first half's name and first row, in one piece.
    sheet.keep(HEADING_HEIGHT + 18 + TILE.height);
    sheet.heading("Ergänzende Auswertung", "Kennzahlen zum Gespräch");

    for (const { label, lead, measurements } of outline.metricGroups) {
      const group = measurements.filter((measurement) => measurement.key !== "loudness");
      if (group.length === 0) continue;

      sheet.keep(18 + TILE.height);
      sheet.paragraph(label, { size: 10.5, style: "bold", colour: NAVY });
      sheet.y += 0.5;
      sheet.paragraph(lead, { size: 8.5, colour: MUTED, lineHeight: 4.2 });
      sheet.y += 4;

      const column = CONTENT_WIDTH / TILE.columns;
      let index = 0;
      let top = sheet.y;
      for (const measurement of group) {
        if (index === 0) {
          sheet.keep(TILE.height);
          top = sheet.y;
        }
        const left = MARGIN.left + index * column;

        doc.setFont("app", "normal");
        doc.setFontSize(8);
        doc.setTextColor(...MUTED);
        doc.setCharSpace(TRACKING);
        doc.text(drawable(measurement.name.toUpperCase()), left, top + 4);
        doc.setCharSpace(0);

        // A checklist names its parts in words, not a count (ADR 0086). Two
        // lines, since the fonts carry no check mark.
        const parts = metricParts(measurement);
        const said = parts?.filter((part) => part.said).map((part) => part.label) ?? [];
        const unsaid = parts?.filter((part) => !part.said).map((part) => part.label) ?? [];

        doc.setFont("app", "bold");
        doc.setFontSize(parts ? 10 : 13);
        doc.setTextColor(...NAVY);
        const value = parts
          ? said.length > 0
            ? said.join(", ")
            : "keiner der Teile erkannt"
          : formatMetricValue(measurement);
        if (parts && doc.getTextWidth(drawable(value)) > column - 3) doc.setFontSize(8.5);
        doc.text(drawable(value), left, top + 10.5);

        const subline =
          parts && unsaid.length > 0 && said.length > 0
            ? `nicht erkannt: ${unsaid.join(", ")}`
            : metricSubline(measurement);
        if (subline) {
          doc.setFont("app", "normal");
          doc.setFontSize(7.5);
          doc.setTextColor(...MUTED);
          doc.text(drawable(subline), left, top + 14.5);
        }

        index = (index + 1) % TILE.columns;
        if (index === 0) sheet.y = top + TILE.height;
      }
      if (index !== 0) sheet.y = top + TILE.height;
      sheet.y += 5;
    }

    const loudness = all.find((measurement) => measurement.key === "loudness");
    const curve = loudness ? loudnessCourse(loudness.detail) : null;
    if (curve) course(loudness!.name, curve);

    sheet.keep(12);
    sheet.paragraph(METRIC_DISCLAIMER, { size: 8.5, colour: MUTED, lineHeight: 4.2 });
    sheet.y += 9;
  }

  /** Drawn as `LoudnessCourse.tsx` draws it; no dB figure, which reads like a level (ADR 0004/0051). */
  function course(name: string, curve: LoudnessCurve) {
    sheet.keep(PLOT_HEIGHT + 30);

    doc.setFont("app", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.text(drawable(`${name} im Gesprächsverlauf`), MARGIN.left, sheet.y);
    sheet.y += 5;

    const top = sheet.y;
    const px = (index: number) => MARGIN.left + (index / (curve.points - 1)) * CONTENT_WIDTH;
    const py = (value: number) =>
      top + PLOT_HEIGHT - ((value - curve.floor) / curve.span) * PLOT_HEIGHT;

    const bandTop = Math.max(top, py(curve.high));
    const bandBottom = Math.min(top + PLOT_HEIGHT, py(curve.low));
    doc.setFillColor(...RULE);
    doc.rect(MARGIN.left, bandTop, CONTENT_WIDTH, Math.max(0.4, bandBottom - bandTop), "F");

    doc.setDrawColor(...MUTED);
    doc.setLineWidth(0.15);
    doc.setLineDashPattern([1, 1.4], 0);
    doc.line(MARGIN.left, py(curve.median), PAGE.width - MARGIN.right, py(curve.median));
    doc.setLineDashPattern([], 0);

    doc.setDrawColor(...BLUE);
    doc.setLineWidth(0.5);
    const step = Math.max(1, Math.ceil(curve.points / PLOT_SEGMENTS));
    for (const run of loudnessRuns(curve.smoothed)) {
      // The run's last point always, or the line ends short.
      const drawn = run.filter((_, i) => i % step === 0 || i === run.length - 1);
      for (let i = 1; i < drawn.length; i++) {
        const from = drawn[i - 1]!;
        const to = drawn[i]!;
        doc.line(px(from), py(curve.smoothed[from]!), px(to), py(curve.smoothed[to]!));
      }
    }

    for (const stretch of curve.stretches) {
      const value = curve.smoothed[stretch.peakIndex];
      if (value === null || value === undefined) continue;
      const at = px(stretch.peakIndex);
      const above = stretch.direction === "louder";
      doc.setFillColor(...BLUE);
      doc.circle(at, py(value), 0.9, "F");

      const caption = `${LOUDNESS_CAPTION[stretch.direction]} · ${loudnessClock(stretch.peakIndex)}`;
      doc.setFont("app", "normal");
      doc.setFontSize(7);
      doc.setTextColor(...NAVY);
      const align =
        at < MARGIN.left + 22 ? "left" : at > PAGE.width - MARGIN.right - 22 ? "right" : "center";
      doc.text(drawable(caption), at, above ? py(value) - 2.4 : py(value) + 4.4, { align });
    }

    sheet.y = top + PLOT_HEIGHT + 4;
    doc.setFont("app", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(...MUTED);
    doc.text("0:00", MARGIN.left, sheet.y);
    doc.text(drawable("Ihre Sprechzeit"), PAGE.width / 2, sheet.y, { align: "center" });
    doc.text(drawable(curve.total), PAGE.width - MARGIN.right, sheet.y, { align: "right" });
    sheet.y += 5;

    sheet.paragraph(
      "Das Band ist der Bereich, in dem Sie die meiste Zeit gesprochen haben; markiert " +
        "ist, wo Sie ihn mindestens zwei Sekunden lang verlassen haben. Gezählt wird nur " +
        "Ihre eigene Sprechzeit, nicht die Dauer des Gesprächs.",
      { size: 8, colour: MUTED, lineHeight: 4 },
    );
    sheet.y += 6;
  }

  /** Last: read closely or not at all. */
  function protocol() {
    sheet.heading("Gespräch im Detail", "Vollständiges Transkript");

    if (transcript.length === 0) {
      sheet.paragraph("Es wurden keine Beiträge aufgezeichnet.", { size: 10, colour: MUTED });
      return;
    }

    for (const entry of transcript) {
      const mine = entry.speaker === "user";
      const colour = mine ? NAVY : BLUE;
      // Before the split: `splitTextToSize` wraps against the current face.
      doc.setFont("app", "normal");
      doc.setFontSize(10);
      const lines: string[] = doc.splitTextToSize(
        drawable(entry.text),
        CONTENT_WIDTH - TEXT_INDENT,
      );

      sheet.keep(LINE_HEIGHT * 2 + 3);

      doc.setFont("app", "bold");
      doc.setFontSize(9);
      doc.setTextColor(...colour);
      doc.text(drawable(mine ? "Sie" : personaName), MARGIN.left + TEXT_INDENT, sheet.y);

      doc.setFont("app", "normal");
      doc.setFontSize(8);
      doc.setTextColor(...MUTED);
      doc.text(formatOffset(entry.offset_ms), MARGIN.left, sheet.y);

      sheet.y += 5;
      doc.setFont("app", "normal");
      doc.setFontSize(10);
      doc.setTextColor(...INK);

      for (const line of lines) {
        if (sheet.y > sheet.bottom) {
          sheet.nextPage();
          // The speaker is named again on the new page.
          doc.setFont("app", "normal");
          doc.setFontSize(8);
          doc.setTextColor(...MUTED);
          doc.text(
            drawable(`${mine ? "Sie" : personaName} (Fortsetzung)`),
            MARGIN.left + TEXT_INDENT,
            sheet.y,
          );
          sheet.y += 5;
          doc.setFont("app", "normal");
          doc.setFontSize(10);
          doc.setTextColor(...INK);
        }
        const stretchTop = sheet.y - 3.4;
        doc.text(line, MARGIN.left + TEXT_INDENT, sheet.y);
        doc.setDrawColor(...colour);
        doc.setLineWidth(0.8);
        doc.line(
          MARGIN.left + TEXT_INDENT - 4,
          stretchTop,
          MARGIN.left + TEXT_INDENT - 4,
          stretchTop + LINE_HEIGHT,
        );
        sheet.y += LINE_HEIGHT;
      }

      sheet.y += 5;
    }
  }

  // No Persona in the name: two trainings with one partner on one day would collide.
  const kind = wrapUp ? "Feedback" : "Protokoll";
  return { doc, filename: `Calltrainer_${kind}_${stamp(date)}.pdf` };
}

export async function downloadFeedbackPdf(options: FeedbackPdfOptions): Promise<void> {
  const { doc, filename } = await buildFeedbackPdf(options);
  doc.save(filename);
}
