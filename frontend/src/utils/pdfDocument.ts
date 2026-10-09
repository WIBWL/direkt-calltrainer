import type { jsPDF } from "jspdf";

import hankenRegular from "../assets/fonts/HankenGrotesk-Regular.ttf";
import hankenSemiBold from "../assets/fonts/HankenGrotesk-SemiBold.ttf";
import schibstedBold from "../assets/fonts/SchibstedGrotesk-Bold.ttf";

/** The chrome shared by `feedbackPdf.ts` (F-68) and `progressPdf.ts` (F-13), palette from `index.css`. */

/** A4, in millimetres. */
export const PAGE = { width: 210, height: 297 };
export const MARGIN = { left: 18, right: 18, top: 18, bottom: 20 };
export const CONTENT_WIDTH = PAGE.width - MARGIN.left - MARGIN.right;

const BANNER_HEIGHT = 36;
export const LINE_HEIGHT = 4.8;

export const NAVY: [number, number, number] = [3, 37, 62];
export const BLUE: [number, number, number] = [50, 95, 127];
export const MUTED: [number, number, number] = [91, 107, 120];
export const RULE: [number, number, number] = [215, 226, 235];
const WHITE: [number, number, number] = [255, 255, 255];
export const INK: [number, number, number] = [30, 40, 50];
/** `is-success` / `is-danger` in index.css. */
export const SUCCESS: [number, number, number] = [34, 96, 72];
export const CAUTION: [number, number, number] = [154, 77, 20];
/** `--color-brand-accent`, for the wordmark's "ai" only. */
const ACCENT: [number, number, number] = [255, 106, 0];

const LOGO_URL = "/logo.png";
/** The logo needs a light ground inside the navy banner. */
const LOGO_TILE = 18;
const LOGO_PAD = 2;

/** In mm, matching `.feedback-section-eyebrow` and `.metric-name`. */
export const TRACKING = 0.2;

/** Eyebrow to rule. */
export const HEADING_HEIGHT = 15;

/** What the subsetted fonts carry; a missing glyph would be an invisible gap. */
const SUPPORTED =
  /[ -~ -ÿĀ-ſ‐-―‘-„†-•…‹›€]/;

/** A guard for emoji or uncovered scripts. */
export function drawable(text: string): string {
  let out = "";
  for (const ch of text) out += SUPPORTED.test(ch) ? ch : "?";
  return out;
}

/** Chunked, or `String.fromCharCode` overruns the argument limit. The status is
 * checked: the SPA answers a miss with a page that would be embedded as a font. */
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

/** Null if missing: the report is worth having without it, unlike without the fonts. */
async function loadLogo(): Promise<string | null> {
  try {
    return `data:image/png;base64,${await loadBase64(LOGO_URL)}`;
  } catch (e) {
    console.debug("[pdf] logo unavailable", e);
    return null;
  }
}

/** "app" (normal, bold) and "display"; both OFL, subsetted to Latin plus German marks. */
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

/** Local parts: `toISOString` would move a late-evening call to the next day. */
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

/** A document written top to bottom; `y` is the one cursor. */
export interface Sheet {
  doc: jsPDF;
  y: number;
  readonly bottom: number;
  nextPage(): void;
  /** Breaks first if `height` does not fit. */
  keep(height: number): void;
  paragraph(text: string, options?: ParagraphOptions): void;
  /** Eyebrow, title and rule, as `SectionHeading` on screen. */
  heading(eyebrow: string, name: string): void;
  facts(rows: [string, string][]): void;
}

/** `title` heads every later page too. */
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

  /** Three runs, because only the "ai" changes colour (`BrandName.tsx`). */
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

  /** Banner on the first page, a rule on every later one. */
  const startPage = (first: boolean) => {
    if (first) {
      doc.setFillColor(...NAVY);
      doc.rect(0, 0, PAGE.width, BANNER_HEIGHT, "F");

      // Without the logo the title block takes the margin back.
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
        // Re-set after a page break.
        doc.setFont("app", style);
        doc.setFontSize(size);
        doc.setTextColor(...colour);
        doc.text(line, MARGIN.left + indent, y);
        y += lineHeight;
      }
    },
    heading(eyebrow: string, name: string) {
      sheet.keep(24);
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
