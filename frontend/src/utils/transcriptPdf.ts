import hankenRegular from "../assets/fonts/HankenGrotesk-Regular.ttf";
import hankenSemiBold from "../assets/fonts/HankenGrotesk-SemiBold.ttf";
import schibstedBold from "../assets/fonts/SchibstedGrotesk-Bold.ttf";
import type { TranscriptEntry } from "../protocol";
import { formatOffset } from "./time";

/**
 * The Gesprächsprotokoll as a PDF, built in the browser (F-64).
 *
 * In the browser and not on the server for one reason that decides it: a
 * training run without consent is never stored (ADR 0066), and that call still
 * shows its transcript. A server route could only serve the calls that were
 * kept, so the one case where the download is the *only* copy is the one case
 * it could not serve. Here the text is already in memory either way, and the
 * spoken content never leaves the machine to become a file.
 *
 * jsPDF is loaded on the press rather than with the app, and so are the fonts:
 * together they are the largest thing the frontend can pull, and most
 * trainings end without anyone wanting a file.
 *
 * The document is set in the app's own faces — Hanken Grotesk for the text,
 * Schibsted Grotesk for the title — rather than in the viewer's Helvetica, so
 * a printed protocol looks like the thing it came out of. Both are under the
 * SIL Open Font License, which permits embedding. They are converted from the
 * bundled woff2 and subsetted to the Latin range plus the marks German text
 * uses; a character outside that subset has no glyph and would come out blank,
 * which is what `drawable` guards against.
 */

/** A4 in millimetres, which is also the unit the document is built in. */
const PAGE = { width: 210, height: 297 };
const MARGIN = { left: 18, right: 18, top: 18, bottom: 20 };
const CONTENT_WIDTH = PAGE.width - MARGIN.left - MARGIN.right;

/** The band at the top of the first page. */
const BANNER_HEIGHT = 36;
/** Where a speaker's text starts, leaving the left column to the timestamp. */
const TEXT_INDENT = 17;
const LINE_HEIGHT = 4.8;

const NAVY: [number, number, number] = [3, 37, 62];
const BLUE: [number, number, number] = [50, 95, 127];
const MUTED: [number, number, number] = [91, 107, 120];
const RULE: [number, number, number] = [215, 226, 235];

export interface TranscriptPdfOptions {
  transcript: TranscriptEntry[];
  /** Shown as the other side of the call, and used in the file name. */
  personaName: string;
  /** When the call happened. Defaults to now, which is right for a call that
   * has just ended — the only screen this is offered on. */
  date?: Date;
}

/** Exactly what the subsetted fonts carry (see the note above). Anything else
 * is dropped rather than drawn: a missing glyph is an invisible gap, and a gap
 * in a transcript is worse than a visible replacement. */
const SUPPORTED =
  /[\u0020-\u007E\u00A0-\u00FF\u0100-\u017F\u2010-\u2015\u2018-\u201E\u2020-\u2022\u2026\u2039\u203A\u20AC]/;

/** Speech transcribed from German or English stays inside the subset, so this
 * is a guard and not a transformation — it only fires on something unexpected,
 * an emoji or a script the fonts do not cover. */
function drawable(text: string): string {
  let out = "";
  for (const ch of text) out += SUPPORTED.test(ch) ? ch : "?";
  return out;
}

/** jsPDF wants a font as base64, and the browser has no direct route from an
 * ArrayBuffer to one. Chunked because `String.fromCharCode` takes its bytes as
 * arguments, and a whole font at once overruns the argument limit. */
async function loadFont(url: string): Promise<string> {
  const bytes = new Uint8Array(await (await fetch(url)).arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  }
  return btoa(binary);
}

/** The app's faces under the two names the document then asks for: "app" in
 * normal and bold, and "display" for the title. */
async function useAppFonts(doc: {
  addFileToVFS: (file: string, data: string) => void;
  addFont: (file: string, name: string, style: string) => void;
}) {
  const faces: [string, string, string, string][] = [
    [hankenRegular, "HankenGrotesk-Regular.ttf", "app", "normal"],
    [hankenSemiBold, "HankenGrotesk-SemiBold.ttf", "app", "bold"],
    [schibstedBold, "SchibstedGrotesk-Bold.ttf", "display", "bold"],
  ];
  const loaded = await Promise.all(faces.map(([url]) => loadFont(url)));
  faces.forEach(([, file, name, style], i) => {
    doc.addFileToVFS(file, loaded[i]!);
    doc.addFont(file, name, style);
  });
}

function formatDate(date: Date): string {
  return date.toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

/** Safe in a file name on every platform, and readable in a download list. */
function slug(text: string): string {
  // Not through `drawable`: this one strips everything but letters and digits
  // anyway, and a "?" standing in for a glyph has no business in a file name.
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/** The document and the name to save it under, without saving it. Separate
 * from the download so the layout can be built and looked at outside a
 * browser — which is how it was designed. */
export async function buildTranscriptPdf({
  transcript,
  personaName,
  date = new Date(),
}: TranscriptPdfOptions) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  await useAppFonts(doc);

  const bottom = PAGE.height - MARGIN.bottom;
  let page = 1;
  let y = 0;

  const footer = () => {
    doc.setFont("app", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.text(
      drawable("Simuliertes Trainingsgespräch mit einer KI - Calltrainer"),
      MARGIN.left,
      PAGE.height - 10,
    );
    doc.text(`Seite ${page}`, PAGE.width - MARGIN.right, PAGE.height - 10, { align: "right" });
  };

  /** The first page carries the banner; every later one a rule, so the
   * transcript keeps running rather than restarting. */
  const startPage = (first: boolean) => {
    if (first) {
      doc.setFillColor(...NAVY);
      doc.rect(0, 0, PAGE.width, BANNER_HEIGHT, "F");
      doc.setTextColor(255, 255, 255);
      doc.setFont("app", "normal");
      doc.setFontSize(9);
      doc.text("CALLTRAINER", MARGIN.left, 15);
      doc.setFont("display", "bold");
      doc.setFontSize(19);
      doc.text("Gesprächsprotokoll", MARGIN.left, 27);
      y = BANNER_HEIGHT + 14;
    } else {
      doc.setDrawColor(...RULE);
      doc.setLineWidth(0.3);
      doc.line(MARGIN.left, MARGIN.top, PAGE.width - MARGIN.right, MARGIN.top);
      doc.setFont("app", "normal");
      doc.setFontSize(8);
      doc.setTextColor(...MUTED);
      doc.text(drawable("Gesprächsprotokoll"), MARGIN.left, MARGIN.top - 3);
      y = MARGIN.top + 10;
    }
    footer();
  };

  const nextPage = () => {
    doc.addPage();
    page += 1;
    startPage(false);
  };

  startPage(true);

  // --- what this call was ------------------------------------------------
  const facts: [string, string][] = [
    ["Gesprächspartner", personaName],
    ["Datum", formatDate(date)],
    ["Beiträge", String(transcript.length)],
  ];
  for (const [label, value] of facts) {
    doc.setFont("app", "normal");
    doc.setFontSize(8);
    doc.setTextColor(...MUTED);
    doc.text(drawable(label.toUpperCase()), MARGIN.left, y);
    doc.setFont("app", "bold");
    doc.setFontSize(11);
    doc.setTextColor(...NAVY);
    doc.text(drawable(value), MARGIN.left + 42, y);
    y += 7;
  }

  y += 4;
  doc.setDrawColor(...RULE);
  doc.setLineWidth(0.4);
  doc.line(MARGIN.left, y, PAGE.width - MARGIN.right, y);
  y += 10;

  if (transcript.length === 0) {
    doc.setFont("app", "normal");
    doc.setFontSize(10);
    doc.setTextColor(...MUTED);
    doc.text(drawable("Es wurden keine Beiträge aufgezeichnet."), MARGIN.left, y);
  }

  // --- the conversation --------------------------------------------------
  for (const entry of transcript) {
    const mine = entry.speaker === "user";
    const colour = mine ? NAVY : BLUE;
    const lines: string[] = doc.splitTextToSize(
      drawable(entry.text),
      CONTENT_WIDTH - TEXT_INDENT,
    );

    // The speaker's line and at least one line of what they said stay
    // together: a name alone at the foot of a page belongs to nothing.
    if (y + LINE_HEIGHT * 2 + 3 > bottom) nextPage();

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
    doc.setTextColor(30, 40, 50);

    for (const line of lines) {
      if (y > bottom) {
        nextPage();
        // Whoever was speaking is named again: a reader who opens the document
        // at this page would otherwise find a paragraph belonging to nobody.
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
        doc.setTextColor(30, 40, 50);
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

  const stamp = date.toISOString().slice(0, 10);
  return { doc, filename: `Gespraechsprotokoll_${stamp}_${slug(personaName)}.pdf` };
}

export async function downloadTranscriptPdf(options: TranscriptPdfOptions): Promise<void> {
  const { doc, filename } = await buildTranscriptPdf(options);
  doc.save(filename);
}
