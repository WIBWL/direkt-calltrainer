import type { jsPDF } from "jspdf";

import hankenRegular from "../assets/fonts/HankenGrotesk-Regular.ttf";
import hankenSemiBold from "../assets/fonts/HankenGrotesk-SemiBold.ttf";
import schibstedBold from "../assets/fonts/SchibstedGrotesk-Bold.ttf";

/**
 * The chrome every PDF this application writes has in common.
 *
 * Two documents are built in the browser: the wrap-up of one call
 * (`feedbackPdf.ts`, F-64) and the progress screen over many
 * (`progressPdf.ts`, F-13). Everything that makes them look like one
 * application is here — the page geometry, the palette taken from `index.css`,
 * the app's own faces, the navy banner with the wordmark on it, the section
 * heading, the wrapped paragraph and the page break. What stays in each
 * document is its own content and the marks only it draws.
 *
 * One module rather than a copy, because the alternative was already visible:
 * a second file repeating the font registration, the banner and the heading,
 * where a change to the letter-spacing of an eyebrow would reach one document
 * and not the other, and nothing would say so.
 *
 * Both are built in the browser, which is a constraint and not a preference:
 * a training run without consent is never stored (ADR 0066) and still shows
 * its transcript, so a server route could not serve the one case where the
 * download is the only copy.
 */

/** A4 in millimetres, which is also the unit a document is built in. */
export const PAGE = { width: 210, height: 297 };
export const MARGIN = { left: 18, right: 18, top: 18, bottom: 20 };
export const CONTENT_WIDTH = PAGE.width - MARGIN.left - MARGIN.right;

/** The band at the top of the first page. */
const BANNER_HEIGHT = 36;
export const LINE_HEIGHT = 4.8;

export const NAVY: [number, number, number] = [3, 37, 62];
export const BLUE: [number, number, number] = [50, 95, 127];
export const MUTED: [number, number, number] = [91, 107, 120];
export const RULE: [number, number, number] = [215, 226, 235];
export const WHITE: [number, number, number] = [255, 255, 255];
export const INK: [number, number, number] = [30, 40, 50];
/** The two tones the feedback page gives its point lists (`is-success` /
 * `is-danger` in index.css). Taken from there rather than invented, so a
 * printed list is the one the reader saw. */
export const SUCCESS: [number, number, number] = [34, 96, 72];
export const CAUTION: [number, number, number] = [154, 77, 20];
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
 * The pages track those out (`letter-spacing` on `.feedback-section-eyebrow`
 * and `.metric-name`); caps set solid read as an abbreviation rather than as a
 * label, which is the whole reason that rule exists on screen.
 */
export const TRACKING = 0.2;

/** What `heading` puts on the page, eyebrow to rule — the room a section
 * needs before anything of its own is drawn. */
export const HEADING_HEIGHT = 15;

/** Exactly what the subsetted fonts carry. Anything else is dropped rather
 * than drawn: a missing glyph is an invisible gap, and a gap in a transcript is
 * worse than a visible replacement. */
const SUPPORTED =
  /[ -~ -ÿĀ-ſ‐-―‘-„†-•…‹›€]/;

/** Speech transcribed from German or English stays inside the subset, so this
 * is a guard and not a transformation — it only fires on something unexpected,
 * an emoji or a script the fonts do not cover. */
export function drawable(text: string): string {
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

/** The logo as a data URL, or null if it cannot be had. A report is worth
 * having without it, so a missing file costs the tile and nothing else — the
 * fonts, which decide how every line of it is set, are deliberately not
 * treated this leniently. */
async function loadLogo(): Promise<string | null> {
  try {
    return `data:image/png;base64,${await loadBase64(LOGO_URL)}`;
  } catch (e) {
    console.debug("[pdf] logo unavailable", e);
    return null;
  }
}

/** The app's faces under the two names a document then asks for: "app" in
 * normal and bold, and "display" for the titles. Both OFL and therefore
 * embeddable, subsetted to Latin plus the marks German uses. */
async function registerAppFonts(doc: jsPDF) {
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

/** The date in a file name: the reader's own day, in the order a downloads
 * list sorts by. Built from the local parts rather than from `toISOString`,
 * which would move a late-evening call to the next day. */
export function stamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}_${pad(date.getMonth() + 1)}_${pad(date.getDate())}`;
}

export interface ParagraphOptions {
  indent?: number;
  size?: number;
  colour?: [number, number, number];
  style?: "normal" | "bold";
  lineHeight?: number;
}

/**
 * A document being written, top to bottom.
 *
 * `y` is the only cursor and the caller moves it; everything that draws
 * something advances it by what it drew. It is an accessor rather than a plain
 * field so that the sheet's own helpers and the caller's marks read and write
 * one number — handing the cursor back and forth as a return value is what a
 * layout written this way gets wrong first.
 */
export interface Sheet {
  doc: jsPDF;
  /** The vertical cursor, in millimetres from the top of the page. */
  y: number;
  /** The last line a page may hold before it has to break. */
  readonly bottom: number;
  /** Start a fresh page, with the running head and the footer on it. */
  nextPage(): void;
  /** Break before drawing something that has to stay in one piece. */
  keep(height: number): void;
  /** Body text, wrapped and broken across pages. */
  paragraph(text: string, options?: ParagraphOptions): void;
  /** A section's heading, the shape `SectionHeading` gives it on screen: the
   *  eyebrow above, the title under it, and a rule closing the row off. */
  heading(eyebrow: string, name: string): void;
  /** The label-and-value rows under the banner: what this document is about,
   *  before anything is said about it. */
  facts(rows: [string, string][]): void;
}

/**
 * A new document with the banner already on it.
 *
 * `title` names the document on the banner and again in the running head of
 * every later page, so a reader who opens it at page four still knows what
 * they are holding.
 */
export async function openSheet(title: string): Promise<Sheet> {
  const { jsPDF: JsPDF } = await import("jspdf");
  const doc = new JsPDF({ unit: "mm", format: "a4" });
  const [, logo] = await Promise.all([registerAppFonts(doc), loadLogo()]);

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

  /** The first page carries the banner; every later one a rule, so a report
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

  const sheet: Sheet = {
    doc,
    get y() {
      return y;
    },
    set y(value: number) {
      y = value;
    },
    bottom,
    nextPage,
    keep(height: number) {
      if (y + height > bottom) nextPage();
    },
    paragraph(
      text: string,
      {
        indent = 0,
        size = 10,
        colour = INK,
        style = "normal",
        lineHeight = LINE_HEIGHT,
      }: ParagraphOptions = {},
    ) {
      doc.setFont("app", style);
      doc.setFontSize(size);
      doc.setTextColor(...colour);
      const lines: string[] = doc.splitTextToSize(drawable(text), CONTENT_WIDTH - indent);
      for (const line of lines) {
        if (y > bottom) nextPage();
        // Re-set after a page break, which leaves the running head's face
        // current.
        doc.setFont("app", style);
        doc.setFontSize(size);
        doc.setTextColor(...colour);
        doc.text(line, MARGIN.left + indent, y);
        y += lineHeight;
      }
    },
    heading(eyebrow: string, name: string) {
      // The heading plus two lines of whatever follows: a title alone at the
      // foot of a page announces nothing.
      sheet.keep(24);
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
    },
    facts(rows: [string, string][]) {
      for (const [label, value] of rows) {
        sheet.keep(9);
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
    },
  };

  startPage(true);
  return sheet;
}
