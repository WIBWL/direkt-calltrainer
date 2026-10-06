import { formatValue } from "../utils/metrics";
import type { SegmentPair } from "../utils/segmentStats";

/** Under pressure against the rest (ADR 0081): no difference, colour or "stable" (ADR 0051).
 * The split is the model's judgement, which the caveat says. */
export default function SegmentComparison({
  pairs,
  caveat = true,
}: {
  pairs: SegmentPair[];
  /** Off where the page already says it. */
  caveat?: boolean;
}) {
  if (pairs.length === 0) return null;

  return (
    <>
      <div className="segment-table-scroll">
        <table className="segment-table">
          <thead>
            <tr>
              <th scope="col">Kennzahl</th>
              <th scope="col" className="segment-value">
                Unter Druck
              </th>
              <th scope="col" className="segment-value">
                Sonst
              </th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((pair) => (
              <tr key={pair.key}>
                <td>{pair.name}</td>
                <td className="segment-value">{figure(pair.key, pair.pressure, pair.unit)}</td>
                <td className="segment-value">{figure(pair.key, pair.rest, pair.unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {caveat && (
        <p className="muted">
          Als fordernd gelten die Stellen, an denen Ihr Gegenüber widersprochen, nachgehakt
          oder etwas verlangt hat. Welche das waren, hat das Sprachmodell beim Schreiben der
          Auswertung bestimmt; die Zahlen daneben sind gemessen. Ein Unterschied zwischen den
          beiden Spalten ist eine Beobachtung und keine Bewertung: Es gibt keinen belegten
          Wert dafür, wie groß er sein darf.
        </p>
      )}
    </>
  );
}

/** A dash, not a zero: nothing was measured there. */
function figure(key: string, value: number | null, unit: string | null): string {
  return value === null ? "–" : formatValue(key, value, unit);
}
