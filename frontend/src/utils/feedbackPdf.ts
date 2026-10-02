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

/** The feedback page as a PDF (F-64), in the page's order with the transcript last;
 * no next steps (paper cannot press them). Built in the browser because an
 * unconsented run is never stored (ADR 0066), so this may be the only copy.
 * Chrome is `pdfDocument.ts`, content `reportOutline.ts`; this file only lays out. */

/** Where a speaker's text starts, leaving the left column to the timestamp.
 * A feedback point that cites an utterance is set on the same two columns, so
 * the timestamps of the report and of the transcript line up. */
const TEXT_INDENT = 17;

/** One statistic's box in the two-column grid. Fixed, so a figure with a
 * second line under it does not make its neighbour sit higher than it. */
const TILE = { columns: 2, height: 16 };
/** The loudness course, drawn at the width of the text (F-37). */
const PLOT_HEIGHT = 26;
/** At most this many segments are drawn for it: the series is one point per
 * 100 ms and already smoothed over a second, so drawing every point of a long
 * call would add thousands of line operations nobody can see. */
const PLOT_SEGMENTS = 240;

export interface FeedbackPdfOptions {
  transcript: TranscriptEntry[];
  /** Shown as the other side of the call, and used in the file name. */
  personaName: string;
  /** The case that was played, named above the Persona: which conversation
   * this was is the first thing a reader of the file needs, and who was on the
   * other end of it only means something once they have that. Left out of the
   * facts entirely where the screen cannot name one. */
  // `| undefined` spelled out because the project builds with
  // `exactOptionalPropertyTypes`, and the screen forwards its own optional
  // prop straight through: that is "may be passed as undefined", not "may be
  // omitted".
  scenarioName?: string | null | undefined;
  /** The stored Session the page was drawn from, or nothing: a call run
   * without consent was never stored (ADR 0066). Its wrap-up may still be
   * missing — failed, or on its way — and the document is then the protocol
   * it used to be, and says so on its banner. The transcript itself is printed
   * from `transcript`, which exists even for a call that was never stored. */
  detail?: SessionDetail | null | undefined;
  /** The focus-goal catalogue, so a point names the goal it was filed under
   * exactly as on screen. */
  goals?: FocusGoal[] | undefined;
  /** When the call happened. Defaults to now, which is right for a call that
   * has just ended — the only screen this is offered on. */
  date?: Date;
}

/** The document and its file name, without saving it, so the layout can be
 * rendered outside a browser. No caller in the repository on purpose (a
 * throwaway render script uses it); an unused-export sweep will flag it wrongly. */
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
  // What the banner and the running head call this. A document without a
  // wrap-up is still only a protocol, and naming it a feedback would promise
  // the one thing it does not have.
  const title = wrapUp ? "Gesprächsfeedback" : "Gesprächsprotokoll";
  const sheet = await openSheet(title);
  const { doc } = sheet;

  // --- what this call was ------------------------------------------------
  const facts: [string, string][] = [
    // The case first: it is what the reader needs in order to place everything
    // under it, the Persona included.
    ...(meta.scenario ? ([["Szenario", meta.scenario]] as [string, string][]) : []),
    ["Gesprächspartner", meta.partner],
    // Which side the User was on: the transcript below reads the other way
    // round in a reverse (ADR 0070), as the page's meta row says too.
    ...(meta.reversal ? ([["Rollentausch", meta.reversal]] as [string, string][]) : []),
    ["Datum", formatLongDate(date.toISOString()) ?? ""],
    ["Beiträge", String(transcript.length)],
  ];
  sheet.facts(facts);
  sheet.y += 7;

  // --- the wrap-up, in the order the page reads in -----------------------
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

  /** One of the two point lists, with the timestamp of the utterance a point
   * cites — the same two columns the transcript is set on, so a reader can
   * find the line a point is about — and the focus goal it was filed under as
   * a small line over it, where `.feedback-point-goal` sets it on screen. */
  function points(
    eyebrow: string,
    name: string,
    list: OutlinePoint[],
    tone: [number, number, number],
  ) {
    if (list.length === 0) return;

    sheet.heading(eyebrow, name);
    for (const point of list) {
      // The timestamp, the goal and the first line of the point stay together.
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
      // The accent bar beside the point, in the colour its list carries on
      // screen: it is what tells the two lists apart once they are printed.
      doc.setDrawColor(...tone);
      doc.setLineWidth(0.8);
      if (sheet.y > top) doc.line(MARGIN.left + 13, top - 3.4, MARGIN.left + 13, sheet.y - 3.4);
      sheet.y += 3.5;
    }
    sheet.y += 6;
  }

  /** The call's statistics (F-53), grouped into the two halves the page's
   * slider switches between — both are printed, because paper has no slider.
   * Never a judgement, only a reading (ADR 0004/0051), which is what the
   * closing line says. */
  function metrics() {
    const all = outline.metricGroups.flatMap((group) => group.measurements);
    if (all.length === 0) return;

    // The heading, the first half's name and its first row of figures in one
    // piece. `heading` keeps room for two lines of body text, which is right
    // for prose and too little here: the first thing under this one is a
    // 16 mm grid, and the heading would sit alone at the foot of the page.
    sheet.keep(HEADING_HEIGHT + 18 + TILE.height);
    sheet.heading("Ergänzende Auswertung", "Kennzahlen zum Gespräch");

    for (const { label, lead, measurements } of outline.metricGroups) {
      const group = measurements.filter((measurement) => measurement.key !== "loudness");
      if (group.length === 0) continue;

      // The half's name, its lead and one row of figures: the name alone at
      // the foot of a page announces a group that is on the next one.
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

        // A checklist metric (the opening, the closing) names its parts in
        // words, as its tile does, rather than printing how many were
        // recognised: "2" alone in display type is the mark ADR 0086 kept off
        // the screen. Smaller than a figure, because it is a list of words. The
        // fonts carry no check mark, so the two states are two lines.
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
        // All three closing parts in a row are wider than half the page at
        // 10pt; one step smaller rather than running into the tile beside it.
        if (parts && doc.getTextWidth(drawable(value)) > column - 3) doc.setFontSize(8.5);
        doc.text(drawable(value), left, top + 10.5);

        // Where parts went unrecognised, that is the second line: it is the
        // half of the checklist a reader would otherwise have to infer.
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

  /** F-37's loudness course, drawn as `LoudnessCourse.tsx` draws it from the same
   * numbers (`utils/loudness.ts`). No figure beside it: the dB span reads like a
   * level without being one (ADR 0004/0051). */
  function course(name: string, curve: LoudnessCurve) {
    // Label, plot, axis and legend in one piece: split across a page the band
    // would be on one and what it means on the next.
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

    // Clamped: on an even call the band is wider than the curve's own range.
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
      // Every `step`-th point, the run's last one always: dropping it would
      // end the line short of where the speaking did.
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
      // Turned in at the edges rather than running off the plot, as on screen.
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

  /** The conversation itself, last in the document: it is read closely or not
   * at all, and everything above comments on it. */
  function protocol() {
    sheet.heading("Gespräch im Detail", "Vollständiges Transkript");

    if (transcript.length === 0) {
      sheet.paragraph("Es wurden keine Beiträge aufgezeichnet.", { size: 10, colour: MUTED });
      return;
    }

    for (const entry of transcript) {
      const mine = entry.speaker === "user";
      const colour = mine ? NAVY : BLUE;
      // Set before the split, not after: `splitTextToSize` wraps against
      // whatever face is current, and the heading above leaves a 14pt one.
      doc.setFont("app", "normal");
      doc.setFontSize(10);
      const lines: string[] = doc.splitTextToSize(
        drawable(entry.text),
        CONTENT_WIDTH - TEXT_INDENT,
      );

      // The speaker's line and at least one line of what they said stay
      // together: a name alone at the foot of a page belongs to nothing.
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
          // Whoever was speaking is named again: a reader who opens the
          // document at this page would otherwise find a paragraph belonging
          // to nobody.
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

  // Named after the app rather than after the call: these files are kept in a
  // downloads folder among everything else, and "Calltrainer" is what the
  // reader will look for. No Persona in it — two trainings on one day with the
  // same partner would collide, and the browser's "(1)" says less than the
  // date does.
  const kind = wrapUp ? "Feedback" : "Protokoll";
  return { doc, filename: `Calltrainer_${kind}_${stamp(date)}.pdf` };
}

export async function downloadFeedbackPdf(options: FeedbackPdfOptions): Promise<void> {
  const { doc, filename } = await buildFeedbackPdf(options);
  doc.save(filename);
}
