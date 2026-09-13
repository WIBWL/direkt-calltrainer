import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Every class in the stylesheet is used by something.
 *
 * The one test here that is not about the live-call audio path, and it earns
 * the exception by being static: it reads two sets of files and compares
 * strings — no jsdom, no fakes, no render.
 *
 * `index.css` is one sheet for 74 components, so a rule outlives the markup
 * that needed it and nothing says so. Fourteen classes had accumulated that
 * way, every one of them residue from a change the project had recorded and
 * shipped: the privacy statement's draft banner after the gaps were filled in,
 * the header's sign-out button after it moved to the profile screen, the brand
 * mark after `BrandName.tsx` took over drawing it, the per-figure method
 * paragraphs ADR 0077 moved behind an "i".
 *
 * Splitting the sheet per component was the alternative and was measured
 * first: 53 of its classes are styled from more than one section — `.card`
 * from twelve — so which rule wins is decided by the order the sheet is
 * concatenated in. Per-component imports would hand that order to the module
 * graph, where neither `tsc` nor this suite nor the production build can see
 * it go wrong. This test buys the part of that refactor that was worth having.
 */

/** Vitest runs with the frontend package as its working directory. Resolving
 *  through `import.meta.url` instead breaks under Vite on Windows, where it
 *  arrives as an `/@fs/` URL with the path still percent-encoded. */
const SRC = join(process.cwd(), "src");

/**
 * Classes assembled at runtime, so the literal never appears in the source.
 *
 * A prefix, the expression that completes it, and where. Listed rather than
 * matched by a pattern: a rule that nothing can reach is exactly what this
 * test is for, and a clever matcher would quietly readmit one.
 */
const BUILT_AT_RUNTIME: ReadonlyArray<readonly [RegExp, string]> = [
  [/^card-origin-/, "LibraryPicker.badgeClass — builtin/own/shared/tenant/reverse/follow-up"],
  [/^call-animation-/, "CallView — the three states of the call animation"],
  [/^dice-face-/, "DiceRoll — the six faces of the die (F-62)"],
  [/^calendar-step-/, "ActivityCalendar — the three-step shade of the activity hue"],
  [/^metric-(value|step)-(green|yellow|red)$/, "the traffic light's colour (ADR 0078)"],
  [/^screen-transition-(cover|reveal)$/, "ScreenTransition — the phase of the cut"],
  [/^reverse-brief-call$/, "the reverse's briefing beside the call (ADR 0070)"],
];

function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) out.push(...sourceFiles(path));
    else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(path);
  }
  return out;
}

/** The stylesheet with its comments removed, so a class named in prose is not
 *  mistaken for one that is styled. */
function stylesheet(): string {
  return readFileSync(join(SRC, "index.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
}

function definedClasses(): string[] {
  return [...new Set(stylesheet().match(/\.-?[_a-zA-Z][\w-]*/g) ?? [])]
    .map((c) => c.slice(1))
    .sort();
}

describe("the stylesheet", () => {
  it("styles nothing the application has stopped rendering", () => {
    const source = sourceFiles(SRC).map((p) => readFileSync(p, "utf8")).join("\n");
    const orphans = definedClasses().filter(
      (cls) => !source.includes(cls) && !BUILT_AT_RUNTIME.some(([re]) => re.test(cls)),
    );
    expect(orphans, "classes in index.css that no component names").toEqual([]);
  });

  it("has an entry under every runtime-built prefix it claims", () => {
    // The allowlist is the one way past the check above, so it has to age with
    // the sheet: a prefix left behind after its rules went would silently widen
    // the exemption for whatever is written next.
    const classes = definedClasses();
    const unused = BUILT_AT_RUNTIME.filter(([re]) => !classes.some((c) => re.test(c)));
    expect(unused.map(([re, why]) => `${re.source} (${why})`)).toEqual([]);
  });
});
