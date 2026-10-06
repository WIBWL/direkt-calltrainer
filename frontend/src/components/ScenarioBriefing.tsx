import type { ReactNode } from "react";

/** "Ihr Wissensstand": the trainee's own side of the case (ADR 0054), never sent to the model. */
export default function ScenarioBriefing({ briefing }: { briefing: string | undefined }) {
  if (!briefing?.trim()) return null;

  return (
    <section className="scenario-briefing">
      <h3 className="scenario-briefing-title">Ihr Wissensstand</h3>
      <StructuredText text={briefing} />
    </section>
  );
}

/** The setup screen's view of a picked card; no figures, which are the Wissensstand's. */
export function ScenarioDescription({ description }: { description: string | undefined }) {
  if (!description?.trim()) return null;

  return (
    <section className="scenario-briefing">
      <h3 className="scenario-briefing-title">Worum es geht</h3>
      <StructuredText text={description} />
    </section>
  );
}

/** `- ` bullets, indented `1. ` sub-items and `**bold**`; anything else is a
 * paragraph. Elements, never HTML: authored text reaches this too. */
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

/** An unpaired marker is left as it is. */
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
