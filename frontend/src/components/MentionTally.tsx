/**
 * How many of the analysed trainings named something, drawn.
 *
 * One pip per analysed training, filled where the theme came up. A count over a
 * denominator of three or eight is what this is, and pips say that where a bar
 * would round it into a proportion and invite reading it as a level. Above
 * `MAX_PIPS` the row of dots stops being countable at a glance, so it becomes a
 * single track instead, which is the lesser evil at that width.
 *
 * Decoration only: the figure stands beside it in words wherever it is used, and
 * this carries `aria-hidden` for that reason. It is a frequency of statements
 * either way, never a measurement and never a score (ADR 0065, ADR 0080).
 *
 * Shared by the recurring block and the focus tiles of the goals with no
 * measurement, which say the same kind of thing and so should look alike: a big
 * "3 von 8" on a tile read as a mark, where the same count as pips reads as
 * what it is.
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
