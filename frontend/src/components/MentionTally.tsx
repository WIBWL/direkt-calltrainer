/**
 * One pip per analysed training, filled where the theme came up: a count, not a proportion or a level (ADR 0065,
 * ADR 0080). Above `MAX_PIPS` it becomes a single track. `aria-hidden`, the figure always stands beside it in
 * words. Shared by the recurring block and unmeasured goals' tiles, where a big "3 von 8" read as a mark.
 */
const MAX_PIPS = 12;

export default function MentionTally({ count, total }: { count: number; total: number }) {
  if (total > MAX_PIPS) {
    const share = total > 0 ? Math.min(1, count / total) : 0;
    return (
      <span className="recurring-track" aria-hidden="true">
        <span className="recurring-track-fill" style={{ width: `${share * 100}%` }} />
      </span>
    );
  }
  return (
    <span className="recurring-pips" aria-hidden="true">
      {Array.from({ length: total }, (_, index) => (
        <span key={index} className={`recurring-pip${index < count ? " is-named" : ""}`} />
      ))}
    </span>
  );
}
