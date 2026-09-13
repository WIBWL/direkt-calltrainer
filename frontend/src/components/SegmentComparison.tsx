import type { SegmentPair } from "../utils/segmentStats";

/**
 * Two figures side by side: how somebody spoke while the other side was
 * pushing back, and how they spoke the rest of the time (ADR 0081, F-62).
 *
 * The one thing this component must not do is answer the question. No
 * difference is shown, nothing is coloured, nothing is called stable or
 * shaky — how large a gap means something is the norm ADR 0051 declines to
 * invent, and this is a screen where one would be very easy to slip in.
 * Two numbers and their labels; the reader compares.
 *
 * The caveat under it is not decoration. Which exchanges were demanding was
 * decided by the language model that wrote the wrap-up, not measured, and a
 * reader who is not told that will take the split for a measurement as exact
 * as the figures sitting on it.
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
              <td className="segment-value">{figure(pair.pressure, pair.unit)}</td>
              <td className="segment-value">{figure(pair.rest, pair.unit)}</td>
            </tr>
          ))}
        </tbody>
      </table>

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

/** A figure, or a dash where that stretch of the call was too short to measure.
 *  A dash and not a zero: nothing was measured there, which is not the same as
 *  having measured nothing. */
function figure(value: number | null, unit: string | null): string {
  if (value === null) return "–";
  const text = value.toFixed(1).replace(".", ",");
  return unit ? `${text} ${unit}` : text;
}
