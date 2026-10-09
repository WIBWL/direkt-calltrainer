import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** ADR 0092: every class in `index.css` is used somewhere. Do not split the sheet: rule order would move into the module graph. */

/** `import.meta.url` breaks under Vite on Windows. */
const SRC = join(process.cwd(), "src");

/** Classes built at runtime; explicit, since a clever matcher would readmit dead rules. */
const BUILT_AT_RUNTIME: ReadonlyArray<readonly [RegExp, string]> = [
  [/^card-origin-/, "LibraryPicker.badgeClass — builtin/own/shared/tenant/reverse/follow-up"],
  [/^call-animation-/, "CallView — the three states of the call animation"],
  [/^dice-face-/, "DiceRoll — the six faces of the die (F-66)"],
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

/** Comments removed, so a class named in prose does not count. */
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
    // A stale prefix would silently widen the exemption.
    const classes = definedClasses();
    const unused = BUILT_AT_RUNTIME.filter(([re]) => !classes.some((c) => re.test(c)));
    expect(unused.map(([re, why]) => `${re.source} (${why})`)).toEqual([]);
  });
});
