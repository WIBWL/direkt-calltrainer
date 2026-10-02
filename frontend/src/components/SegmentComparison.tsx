import { formatValue } from "../utils/metrics";
import type { SegmentPair } from "../utils/segmentStats";

/**
 * Two figures side by side: under pressure vs the rest of the call (ADR 0081, F-62). Shows no difference, no
 * colour, no "stable" — how large a gap matters is the norm ADR 0051 declines. The caveat under it matters: the
 * split was the language model's judgement, not a measurement.
 */
export default function SegmentComparison({
  pairs,
  caveat = true,
}: {
  pairs: SegmentPair[];
  /** Off where the surrounding page already says where the split comes from,
   *  so the same sentence does not appear twice on one screen. */
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

/** A figure as every other screen reads it, or a dash where that stretch of the
 *  call was too short to measure. A dash and not a zero: nothing was measured
 *  there, which is not the same as having measured nothing. */
function figure(key: string, value: number | null, unit: string | null): string {
  return value === null ? "–" : formatValue(key, value, unit);
}
