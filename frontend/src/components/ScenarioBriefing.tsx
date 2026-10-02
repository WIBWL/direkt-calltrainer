import type { ReactNode } from "react";

/**
 * The trainee's own side of the case (ADR 0054), shown as "Ihr Wissensstand" — the only text addressed to
 * whoever picks up, not to the model. Rendered after the microphone check and again with the call, where one
 * reaches back for a number mid-sentence, hence a built-in's `- ` list (`StructuredText`). Renders nothing for
 * a Scenario without one.
 */
export default function ScenarioBriefing({ briefing }: { briefing: string | undefined }) {
  if (!briefing?.trim()) return null;

  return (
    <section className="scenario-briefing">
      <h3 className="scenario-briefing-title">Ihr Wissensstand</h3>
      <StructuredText text={briefing} />
    </section>
  );
}

/**
 * What the setup screen shows once a card is picked: who calls, why, in what
 * situation and what is practised. No figures — those are the Wissensstand's,
 * read once the Session is committed to.
 */
export function ScenarioDescription({ description }: { description: string | undefined }) {
  if (!description?.trim()) return null;

  return (
    <section className="scenario-briefing">
      <h3 className="scenario-briefing-title">Worum es geht</h3>
      <StructuredText text={description} />
    </section>
  );
}

/**
 * Plain text with the little structure the seeded briefings use, and nothing
 * more: a line starting `- ` is a bullet, an indented `1. ` line under one is a
 * numbered sub-item, `**x**` is bold. Anything else is a paragraph, so a
 * briefing an author or the follow-up generator wrote as prose reads exactly as
 * it always did. Rendered as elements, never as HTML — authored text reaches
 * this component too.
 */
export function StructuredText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let bullets: { text: string; sub: string[] }[] = [];

  const flush = () => {
    if (bullets.length === 0) return;
    blocks.push(
      <ul className="scenario-briefing-list" key={blocks.length}>
        {bullets.map((item, i) => (
          <li key={i}>
            {inline(item.text)}
            {item.sub.length > 0 && (
              <ol>
                {item.sub.map((sub, j) => (
                  <li key={j}>{inline(sub)}</li>
                ))}
              </ol>
            )}
          </li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const line of text.split("\n")) {
    const sub = /^\s+\d+\.\s+(.*)$/.exec(line);
    const parent = bullets[bullets.length - 1];
    if (line.startsWith("- ")) {
      bullets.push({ text: line.slice(2), sub: [] });
    } else if (sub && parent) {
      parent.sub.push(sub[1] ?? "");
    } else if (line.trim()) {
      flush();
      blocks.push(
        <p className="scenario-briefing-body" key={blocks.length}>
          {inline(line)}
        </p>,
      );
    }
  }
  flush();

  return <>{blocks}</>;
}

/** `**bold**` inside one line; an unpaired marker is left as it is. */
function inline(line: string): ReactNode[] {
  return line
    .split(/(\*\*[^*]+\*\*)/)
    .map((part, i) =>
      part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
        <strong key={i}>{part.slice(2, -2)}</strong>
      ) : (
        part
      ),
    );
}
