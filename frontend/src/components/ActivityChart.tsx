import type { ActivityBucket } from "../utils/progressStats";

/**
 * How often the user trained across the period (F-13).
 *
 * The one chart on this screen that says something even when barely anything
 * has been measured yet, because it only needs the dates. It is also the one
 * chart ADR 0065 permits without any qualification: activity counts what
 * somebody did, not how well they did it, so no norm is being implied and no
 * threshold is being invented.
 *
 * Abandoned calls are a lighter shade of the same colour rather than a second,
 * warning-coloured one. That a call was broken off is a fact worth seeing, and
 * the history states it the same neutral way. Red would turn it into a mark.
 *
 * Bars rather than a line: the value is a count per period, and a line between
 * counts would suggest the values in between mean something.
 */
export default function ActivityChart({ buckets }: { buckets: ActivityBucket[] }) {
  if (buckets.length === 0) return null;

  const total = (b: ActivityBucket) => b.completed + b.aborted;
  const peak = Math.max(1, ...buckets.map(total));
  // Every bar keeps a visible foot, so an empty period reads as "nothing here"
  // rather than as a rendering gap.
  const height = (count: number) => (count === 0 ? 0 : Math.max(6, (count / peak) * 100));

  // A long period is unreadable if every bar is labelled; a handful of dates is
  // enough to place the chart in time.
  const labelEvery = Math.max(1, Math.ceil(buckets.length / 8));
  const sessions = buckets.reduce((sum, b) => sum + total(b), 0);

  return (
    <figure className="activity-chart">
      <div
        className="activity-bars"
        role="img"
        aria-label={
          `Trainings über die Zeit: ${sessions} insgesamt, verteilt auf ${buckets.length} ` +
          `Abschnitte, am meisten ${peak} in einem Abschnitt.`
        }
      >
        {buckets.map((bucket) => (
          <div className="activity-bar-slot" key={bucket.from}>
            <span className="activity-bar-count">{total(bucket) || ""}</span>
            <div className="activity-bar-stack">
              {bucket.aborted > 0 && (
                <span
                  className="activity-bar activity-bar-aborted"
                  style={{ height: `${height(bucket.aborted)}%` }}
                />
              )}
              {bucket.completed > 0 && (
                <span
                  className="activity-bar"
                  style={{ height: `${height(bucket.completed)}%` }}
                />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="activity-axis" aria-hidden="true">
        {buckets.map((bucket, index) => (
          <span key={bucket.from}>{index % labelEvery === 0 ? bucket.label : ""}</span>
        ))}
      </div>

      <figcaption className="activity-legend">
        <span className="activity-key" />
        abgeschlossen
        <span className="activity-key activity-key-aborted" />
        abgebrochen
      </figcaption>
    </figure>
  );
}
