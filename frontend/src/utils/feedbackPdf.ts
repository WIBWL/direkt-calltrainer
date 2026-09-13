import hankenRegular from "../assets/fonts/HankenGrotesk-Regular.ttf";
import hankenSemiBold from "../assets/fonts/HankenGrotesk-SemiBold.ttf";
import schibstedBold from "../assets/fonts/SchibstedGrotesk-Bold.ttf";
import type {
  Measurement,
  SessionFeedback,
  SessionTurn,
  TranscriptEntry,
} from "../protocol";
import {
  analyseLoudness,
  loudnessClock,
  loudnessRuns,
  LOUDNESS_CAPTION,
  type LoudnessCurve,
} from "./loudness";
import {
  ASPECT_LABELS,
  ASPECT_LEADS,
  formatMetricValue,
  loudnessCurve,
  METRIC_ASPECTS,
  METRIC_DISCLAIMER,
  metricAspect,
  metricParts,
  metricSubline,
  withDerived,
} from "./metrics";
import { formatLongDate, formatOffset } from "./time";

/**
 * The whole feedback document as a PDF, built in the browser (F-64).
 *
 * Carries everything the feedback page shows, in the page's own order —
 * summary, strengths, improvements, phase-appropriate register, metrics — with
 * the transcript last, for the same reason it is collapsed on screen: it is
 * read closely or not at all, and a document opening with it buries everything
 * that comments on it.
 *
 * The next-steps block is deliberately absent: those two offers write a new
 * Scenario when pressed, and a sheet of paper cannot press them.
 *
 * Built in the browser and not on the server for the one reason that decides
 * it: a training run without consent is never stored (ADR 0066) and still shows
 * its transcript, so the one case where this download is the *only* copy is the
 * one case a server route could not serve.
 *
 * jsPDF and the fonts are fetched on the press — together the largest thing the
 * frontend can pull, and most trainings end without anyone wanting a file.
 *
 * Set in the app's own faces (Hanken Grotesk, Schibsted Grotesk for titles)
 * rather than the viewer's Helvetica, both OFL and therefore embeddable. They
 * are subsetted to Latin plus the marks German uses; a character outside that
 * subset would come out blank, which is what `drawable` guards against.
 */

/** A4 in millimetres, which is also the unit the document is built in. */
const PAGE = { width: 210, height: 297 };
const MARGIN = { left: 18, right: 18, top: 18, bottom: 20 };
const CONTENT_WIDTH = PAGE.width - MARGIN.left - MARGIN.right;

/** The band at the top of the first page. */
const BANNER_HEIGHT = 36;
/** Where a speaker's text starts, leaving the left column to the timestamp.
 * A feedback point that cites an utterance is set on the same two columns, so
 * the timestamps of the report and of the transcript line up. */
const TEXT_INDENT = 17;
const LINE_HEIGHT = 4.8;

const NAVY: [number, number, number] = [3, 37, 62];
const BLUE: [number, number, number] = [50, 95, 127];
const MUTED: [number, number, number] = [91, 107, 120];
const RULE: [number, number, number] = [215, 226, 235];
const WHITE: [number, number, number] = [255, 255, 255];
const INK: [number, number, number] = [30, 40, 50];
/** The two tones the feedback page gives its point lists (`is-success` /
 * `is-danger` in index.css). Taken from there rather than invented, so a
 * printed list is the one the reader saw. */
const SUCCESS: [number, number, number] = [34, 96, 72];
const CAUTION: [number, number, number] = [154, 77, 20];
/** `--color-brand-accent`. The one place it is allowed here: the "ai" of the
 * wordmark, exactly as on screen (see `BrandName.tsx`). */
const ACCENT: [number, number, number] = [255, 106, 0];

/** The logo is a file in `public/` rather than a bundled asset, so it is
 * fetched by the same path the header's <img> uses. */
const LOGO_URL = "/logo.png";
/** The white tile the logo sits on inside the navy banner. Its strokes are
 * navy and blue, so it needs a light ground to be visible at all — the same
 * answer the favicon gives. */
const LOGO_TILE = 18;
const LOGO_PAD = 2;

/**
 * How far apart the letters of a small uppercase line are set, in millimetres.
 * The page tracks those out (`letter-spacing` on `.feedback-section-eyebrow`
 * and `.metric-name`); caps set solid read as an abbreviation rather than as a
 * label, which is the whole reason that rule exists on screen.
 */
const TRACKING = 0.2;

/** What `heading` puts on the page, eyebrow to rule — the room a section
 * needs before anything of its own is drawn. */
const HEADING_HEIGHT = 15;
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
  /** The wrap-up as the page shows it, or nothing: a call run without consent
   * has none (ADR 0066), and neither has one whose generation failed. The
   * document is then the protocol it used to be, and says so on its banner. */
  feedback?: SessionFeedback | null | undefined;
  /** The call's statistics (F-53). Present without a wrap-up as well — they
   * are measured during the call and stored with the Session. */
  measurements?: Measurement[] | undefined;
  /** The stored utterances, used for one thing only: a feedback point that
   * names a Turn carries that Turn's timestamp, exactly as on screen. The
   * transcript itself is printed from `transcript`, which exists even for a
   * call that was never stored. */
  turns?: SessionTurn[] | undefined;
  /** When the call happened. Defaults to now, which is right for a call that
   * has just ended — the only screen this is offered on. */
  date?: Date;
}

/** Exactly what the subsetted fonts carry (see the note above). Anything else
 * is dropped rather than drawn: a missing glyph is an invisible gap, and a gap
 * in a transcript is worse than a visible replacement. */
const SUPPORTED =
  /[ -~ -ÿĀ-ſ‐-―‘-„†-•…‹›€]/;

/** Speech transcribed from German or English stays inside the subset, so this
 * is a guard and not a transformation — it only fires on something unexpected,
 * an emoji or a script the fonts do not cover. */
function drawable(text: string): string {
  let out = "";
  for (const ch of text) out += SUPPORTED.test(ch) ? ch : "?";
  return out;
}

/** jsPDF wants a font and an image as base64, and the browser has no direct
 * route from an ArrayBuffer to one. Chunked because `String.fromCharCode` takes
 * its bytes as arguments, and a whole font at once overruns the argument limit.
 * The status is checked because a miss under the SPA is still a response with a
 * body, which would otherwise be base64ed into the document as a font. */
async function loadBase64(url: string): Promise<string> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  }
  return btoa(binary);
}

/** The logo as a data URL, or null if it cannot be had. The report is worth
 * having without it, so a missing file costs the tile and nothing else — the
 * fonts, which decide how every line of it is set, are deliberately not
 * treated this leniently. */
async function loadLogo(): Promise<string | null> {
  try {
    return `data:image/png;base64,${await loadBase64(LOGO_URL)}`;
  } catch (e) {
    console.debug("[feedback pdf] logo unavailable", e);
    return null;
  }
}

/** The app's faces under the two names the document then asks for: "app" in
 * normal and bold, and "display" for the titles. */
async function useAppFonts(doc: {
  addFileToVFS: (file: string, data: string) => void;
  addFont: (file: string, name: string, style: string) => void;
}) {
  const faces: [string, string, string, string][] = [
    [hankenRegular, "HankenGrotesk-Regular.ttf", "app", "normal"],
    [hankenSemiBold, "HankenGrotesk-SemiBold.ttf", "app", "bold"],
    [schibstedBold, "SchibstedGrotesk-Bold.ttf", "display", "bold"],
  ];
  const loaded = await Promise.all(faces.map(([url]) => loadBase64(url)));
  faces.forEach(([, file, name, style], i) => {
    doc.addFileToVFS(file, loaded[i]!);
    doc.addFont(file, name, style);
  });
}

/** The date in the file name: the call's own day, in the reader's zone and in
 * the order a download list sorts by. Built from the local parts rather than
 * from `toISOString`, which would move a late-evening call to the next day. */
function stamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}_${pad(date.getMonth() + 1)}_${pad(date.getDate())}`;
}

/** The document and the name to save it under, without saving it. Separate
 * from the download so the layout can be built and looked at outside a
 * browser — which is how it was designed. */
export async function buildFeedbackPdf({
  transcript,
  personaName,
  scenarioName,
  feedback,
  measurements = [],
  turns = [],
  date = new Date(),
}: FeedbackPdfOptions) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const [, logo] = await Promise.all([useAppFonts(doc), loadLogo()]);

  // What the banner and the running head call this. A document without a
  // wrap-up is still only a protocol, and naming it a feedback would promise
  // the one thing it does not have.
  const title = feedback ? "Gesprächsfeedback" : "Gesprächsprotokoll";
  const bottom = PAGE.height - MARGIN.bottom;
  let page = 1;
  let y = 0;

  const footer = () => {
    doc.setFont("app", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.text(`Seite ${page}`, PAGE.width - MARGIN.right, PAGE.height - 10, { align: "right" });
  };

  /** The wordmark, set the way the app sets it: the display face, and the "ai"
   * in the brand accent (`BrandName.tsx`). Three runs rather than one string,
   * because only the middle one changes colour. It used to be a line of flat
   * uppercase body text, which read as a label rather than as the mark it is. */
  const wordmark = (x: number, baseline: number) => {
    doc.setFont("display", "bold");
    doc.setFontSize(11);
    let cursor = x;
    const runs: [string, [number, number, number]][] = [
      ["Calltr", WHITE],
      ["ai", ACCENT],
      ["ner", WHITE],
    ];
    for (const [text, colour] of runs) {
      doc.setTextColor(...colour);
      doc.text(text, cursor, baseline);
      cursor += doc.getTextWidth(text);
    }
  };

  /** The first page carries the banner; every later one a rule, so the report
   * keeps running rather than restarting. */
  const startPage = (first: boolean) => {
    if (first) {
      doc.setFillColor(...NAVY);
      doc.rect(0, 0, PAGE.width, BANNER_HEIGHT, "F");

      // The logo centred in the band, the title block set beside it. Without
      // the logo that block simply takes the margin back, so a failed fetch
      // leaves a banner that still looks deliberate.
      const tileTop = (BANNER_HEIGHT - LOGO_TILE) / 2;
      let textLeft = MARGIN.left;
      if (logo) {
        doc.setFillColor(...WHITE);
        doc.roundedRect(MARGIN.left, tileTop, LOGO_TILE, LOGO_TILE, 4, 4, "F");
        doc.addImage(
          logo,
          "PNG",
          MARGIN.left + LOGO_PAD,
          tileTop + LOGO_PAD,
          LOGO_TILE - LOGO_PAD * 2,
          LOGO_TILE - LOGO_PAD * 2,
        );
        textLeft = MARGIN.left + LOGO_TILE + 8;
      }

      wordmark(textLeft, 15);
      doc.setTextColor(...WHITE);
      doc.setFont("display", "bold");
      doc.setFontSize(19);
      doc.text(drawable(title), textLeft, 26);
      y = BANNER_HEIGHT + 14;
    } else {
      doc.setDrawColor(...RULE);
      doc.setLineWidth(0.3);
      doc.line(MARGIN.left, MARGIN.top, PAGE.width - MARGIN.right, MARGIN.top);
      doc.setFont("app", "normal");
      doc.setFontSize(8);
      doc.setTextColor(...MUTED);
      doc.text(drawable(title), MARGIN.left, MARGIN.top - 3);
      y = MARGIN.top + 10;
    }
    footer();
  };

  const nextPage = () => {
    doc.addPage();
    page += 1;
    startPage(false);
  };

  /** Break before drawing something that has to stay in one piece. */
  const keep = (height: number) => {
    if (y + height > bottom) nextPage();
  };

  /** Body text, wrapped and broken across pages. Returns nothing: everything
   * here is laid out top to bottom, and `y` is the only cursor. */
  const paragraph = (
    text: string,
    {
      indent = 0,
      size = 10,
      colour = INK,
      style = "normal",
      lineHeight = LINE_HEIGHT,
    }: {
      indent?: number;
      size?: number;
      colour?: [number, number, number];
      style?: "normal" | "bold";
      lineHeight?: number;
    } = {},
  ) => {
    doc.setFont("app", style);
    doc.setFontSize(size);
    doc.setTextColor(...colour);
    const lines: string[] = doc.splitTextToSize(drawable(text), CONTENT_WIDTH - indent);
    for (const line of lines) {
      if (y > bottom) nextPage();
      doc.setFont("app", style);
      doc.setFontSize(size);
      doc.setTextColor(...colour);
      doc.text(line, MARGIN.left + indent, y);
      y += lineHeight;
    }
  };

  /** A section's heading, the same shape the page gives it (`SectionHeading`):
   * the eyebrow above, the title under it, and a rule closing the row off. */
  const heading = (eyebrow: string, name: string) => {
    // The heading plus two lines of whatever follows: a title alone at the
    // foot of a page announces nothing.
    keep(24);
    // Blue and tracked out, as `.feedback-section-eyebrow` is on screen —
    // not muted grey. The eyebrow is the section's label, and a grey one
    // reads as a footnote to the title under it.
    doc.setFont("app", "bold");
    doc.setFontSize(7.5);
    doc.setTextColor(...BLUE);
    doc.setCharSpace(TRACKING);
    doc.text(drawable(eyebrow.toUpperCase()), MARGIN.left, y);
    doc.setCharSpace(0);
    y += 5.6;
    doc.setFont("display", "bold");
    doc.setFontSize(14);
    doc.setTextColor(...NAVY);
    doc.text(drawable(name), MARGIN.left, y);
    y += 2.8;
    doc.setDrawColor(...RULE);
    doc.setLineWidth(0.4);
    doc.line(MARGIN.left, y, PAGE.width - MARGIN.right, y);
    y += 6.5;
  };

  startPage(true);

  // --- what this call was ------------------------------------------------
  const facts: [string, string][] = [
    // The case first: it is what the reader needs in order to place everything
    // under it, the Persona included.
    ...(scenarioName ? ([["Szenario", scenarioName]] as [string, string][]) : []),
    ["Gesprächspartner", personaName],
    ["Datum", formatLongDate(date.toISOString()) ?? ""],
    ["Beiträge", String(transcript.length)],
  ];
  for (const [label, value] of facts) {
    doc.setFont("app", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.setCharSpace(TRACKING);
    doc.text(drawable(label.toUpperCase()), MARGIN.left, y);
    doc.setCharSpace(0);
    doc.setFont("app", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...NAVY);
    doc.text(drawable(value), MARGIN.left + 42, y);
    y += 7;
  }
  y += 7;

  // --- the wrap-up, in the order the page reads in -----------------------
  if (feedback) {
    heading("Qualitative Einordnung", "Zusammenfassung");
    paragraph(feedback.summary);
    y += 9;

    points("Stärken", "Das gelang gut", "strength");
    points("Weiterentwickeln", "Das können Sie verbessern", "improvement");

    if (feedback.phase_language) {
      heading("Gesprächsführung", "Phasengerechte Sprache");
      paragraph(feedback.phase_language);
      y += 2.5;
      paragraph("Warm einsteigen, sachlich am Anliegen arbeiten, warm abschließen.", {
        size: 9,
        colour: MUTED,
        lineHeight: 4.4,
      });
      y += 9;
    }
  }

  metrics();
  protocol();

  /** One of the two point lists, with the timestamp of the utterance a point
   * cites — the same two columns the transcript is set on, so a reader can
   * find the line a point is about. */
  function points(eyebrow: string, name: string, kind: "strength" | "improvement") {
    const list = feedback?.points.filter((point) => point.kind === kind) ?? [];
    if (list.length === 0) return;

    heading(eyebrow, name);
    for (const point of list) {
      const turn =
        point.turn_id !== null
          ? turns.find((candidate) => candidate.turn_id === point.turn_id)
          : undefined;

      // The timestamp and the first line of its point stay together.
      keep(LINE_HEIGHT * 2);
      if (turn) {
        doc.setFont("app", "normal");
        doc.setFontSize(8);
        doc.setTextColor(...MUTED);
        doc.text(formatOffset(turn.start_offset_ms), MARGIN.left, y);
      }
      const top = y;
      paragraph(point.text, { indent: TEXT_INDENT });
      // The accent bar beside the point, in the colour its list carries on
      // screen: it is what tells the two lists apart once they are printed.
      doc.setDrawColor(...(kind === "strength" ? SUCCESS : CAUTION));
      doc.setLineWidth(0.8);
      if (y > top) doc.line(MARGIN.left + 13, top - 3.4, MARGIN.left + 13, y - 3.4);
      y += 3.5;
    }
    y += 6;
  }

  /** The call's statistics (F-53), grouped into the two halves the page's
   * slider switches between — both are printed, because paper has no slider.
   * Never a judgement, only a reading (ADR 0004/0051), which is what the
   * closing line says. */
  function metrics() {
    const all = withDerived(measurements);
    if (all.length === 0) return;

    // The heading, the first half's name and its first row of figures in one
    // piece. `heading` keeps room for two lines of body text, which is right
    // for prose and too little here: the first thing under this one is a
    // 16 mm grid, and the heading would sit alone at the foot of the page.
    keep(HEADING_HEIGHT + 18 + TILE.height);
    heading("Ergänzende Auswertung", "Kennzahlen zum Gespräch");

    for (const aspect of METRIC_ASPECTS) {
      const group = all.filter(
        (measurement) => metricAspect(measurement) === aspect && measurement.key !== "loudness",
      );
      if (group.length === 0) continue;

      // The half's name, its lead and one row of figures: the name alone at
      // the foot of a page announces a group that is on the next one.
      keep(18 + TILE.height);
      paragraph(ASPECT_LABELS[aspect], { size: 10.5, style: "bold", colour: NAVY });
      y += 0.5;
      paragraph(ASPECT_LEADS[aspect], { size: 8.5, colour: MUTED, lineHeight: 4.2 });
      y += 4;

      const column = CONTENT_WIDTH / TILE.columns;
      let index = 0;
      let top = y;
      for (const measurement of group) {
        if (index === 0) {
          keep(TILE.height);
          top = y;
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
        if (index === 0) y = top + TILE.height;
      }
      if (index !== 0) y = top + TILE.height;
      y += 5;
    }

    const loudness = all.find((measurement) => measurement.key === "loudness");
    const values = loudness ? loudnessCurve(loudness) : null;
    const curve = values ? analyseLoudness(values) : null;
    if (curve) course(loudness!.name, curve);

    keep(12);
    paragraph(METRIC_DISCLAIMER, { size: 8.5, colour: MUTED, lineHeight: 4.2 });
    y += 9;
  }

  /** F-37's loudness course, drawn the way `LoudnessCourse.tsx` draws it and
   * from the same numbers (`utils/loudness.ts`): the band the call spent most
   * of its time in, the median through it, the smoothed line, and the at most
   * two stretches that left the band for longer than two seconds. No figure
   * accompanies it — the Measurement's value is a dB span that reads like a
   * level without being one (ADR 0004/0051). */
  function course(name: string, curve: LoudnessCurve) {
    // Label, plot, axis and legend in one piece: split across a page the band
    // would be on one and what it means on the next.
    keep(PLOT_HEIGHT + 30);

    doc.setFont("app", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.text(drawable(`${name} im Gesprächsverlauf`), MARGIN.left, y);
    y += 5;

    const top = y;
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

    y = top + PLOT_HEIGHT + 4;
    doc.setFont("app", "normal");
    doc.setFontSize(7.5);
    doc.setTextColor(...MUTED);
    doc.text("0:00", MARGIN.left, y);
    doc.text(drawable("Ihre Sprechzeit"), PAGE.width / 2, y, { align: "center" });
    doc.text(drawable(curve.total), PAGE.width - MARGIN.right, y, { align: "right" });
    y += 5;

    paragraph(
      "Das Band ist der Bereich, in dem Sie die meiste Zeit gesprochen haben; markiert " +
        "ist, wo Sie ihn mindestens zwei Sekunden lang verlassen haben. Gezählt wird nur " +
        "Ihre eigene Sprechzeit, nicht die Dauer des Gesprächs.",
      { size: 8, colour: MUTED, lineHeight: 4 },
    );
    y += 6;
  }

  /** The conversation itself, last in the document: it is read closely or not
   * at all, and everything above comments on it. */
  function protocol() {
    heading("Gespräch im Detail", "Vollständiges Transkript");

    if (transcript.length === 0) {
      paragraph("Es wurden keine Beiträge aufgezeichnet.", { size: 10, colour: MUTED });
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
      keep(LINE_HEIGHT * 2 + 3);

      doc.setFont("app", "bold");
      doc.setFontSize(9);
      doc.setTextColor(...colour);
      doc.text(drawable(mine ? "Sie" : personaName), MARGIN.left + TEXT_INDENT, y);

      doc.setFont("app", "normal");
      doc.setFontSize(8);
      doc.setTextColor(...MUTED);
      doc.text(formatOffset(entry.offset_ms), MARGIN.left, y);

      y += 5;
      doc.setFont("app", "normal");
      doc.setFontSize(10);
      doc.setTextColor(...INK);

      for (const line of lines) {
        if (y > bottom) {
          nextPage();
          // Whoever was speaking is named again: a reader who opens the
          // document at this page would otherwise find a paragraph belonging
          // to nobody.
          doc.setFont("app", "normal");
          doc.setFontSize(8);
          doc.setTextColor(...MUTED);
          doc.text(
            drawable(`${mine ? "Sie" : personaName} (Fortsetzung)`),
            MARGIN.left + TEXT_INDENT,
            y,
          );
          y += 5;
          doc.setFont("app", "normal");
          doc.setFontSize(10);
          doc.setTextColor(...INK);
        }
        const stretchTop = y - 3.4;
        doc.text(line, MARGIN.left + TEXT_INDENT, y);
        doc.setDrawColor(...colour);
        doc.setLineWidth(0.8);
        doc.line(
          MARGIN.left + TEXT_INDENT - 4,
          stretchTop,
          MARGIN.left + TEXT_INDENT - 4,
          stretchTop + LINE_HEIGHT,
        );
        y += LINE_HEIGHT;
      }

      y += 5;
    }
  }

  // Named after the app rather than after the call: these files are kept in a
  // downloads folder among everything else, and "Calltrainer" is what the
  // reader will look for. No Persona in it — two trainings on one day with the
  // same partner would collide, and the browser's "(1)" says less than the
  // date does.
  const kind = feedback ? "Feedback" : "Protokoll";
  return { doc, filename: `Calltrainer_${kind}_${stamp(date)}.pdf` };
}

export async function downloadFeedbackPdf(options: FeedbackPdfOptions): Promise<void> {
  const { doc, filename } = await buildFeedbackPdf(options);
  doc.save(filename);
}
