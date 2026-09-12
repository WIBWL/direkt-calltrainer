import { useMemo, useState } from "react";

import type { SessionSummary } from "../protocol";
import {
  activityMonth,
  activityStep,
  firstTrainingMonth,
  type ActivityDay,
} from "../utils/progressStats";

/**
 * When the user trained, on a calendar (F-13).
 *
 * A calendar rather than the bar-per-day that stood here first: the numbers are
 * the same, but only a calendar carries the shape of a week — whether trainings
 * sit on workdays, whether a fortnight went untouched, whether they cluster
 * before a deadline.
 *
 * One month at a time, paged back to the oldest stored training. Six months as
 * small multiples was a wall of grids in which the wanted month was the hardest
 * to find, and it left the block beside it against half a metre of border.
 *
 * The period switch deliberately does not reach this block, and says so by
 * standing *below* it: a calendar carries its own range in the grid, so cutting
 * months off it would state the same thing twice, as a hole in a chart.
 *
 * The one block here needing no caveat — counting what somebody did implies no
 * norm (ADR 0065). The shading is magnitude, one hue in three steps because a
 * day holds one, two or a handful of calls; the count is printed in the cell,
 * so colour is redundant rather than the carrier.
 *
 * A real `<table>` with a caption per month: a calendar *is* tabular, so a
 * screen reader gets the weekday and the count from the markup rather than from
 * a label somebody has to keep in step.
 */

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const WEEKDAY_NAMES = [
  "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag",
];

export default function ActivityCalendar({ sessions }: { sessions: SessionSummary[] }) {
  const today = new Date();
  const [shown, setShown] = useState({
    year: today.getFullYear(),
    month: today.getMonth(),
  });
  const [active, setActive] = useState<ActivityDay | null>(null);

  const month = useMemo(
    () => activityMonth(sessions, shown.year, shown.month),
    [sessions, shown.year, shown.month],
  );
  const earliest = useMemo(() => firstTrainingMonth(sessions), [sessions]);

  // Months counted from year zero, so "is this one before that one" is one
  // comparison instead of two nested ones.
  const at = shown.year * 12 + shown.month;
  const hasPrevious = earliest !== null && at > earliest.year * 12 + earliest.month;
  const hasNext = at < today.getFullYear() * 12 + today.getMonth();
  const todayKey = dayId(today);

  const step = (by: number) => {
    // The readout names a day of the month on screen; paging away from it would
    // otherwise leave that sentence standing over a different month.
    setActive(null);
    setShown(({ year, month: current }) => {
      const moved = new Date(year, current + by, 1);
      return { year: moved.getFullYear(), month: moved.getMonth() };
    });
  };

  return (
    <figure className="calendar">
      <div className="calendar-head">
        <button
          type="button"
          className="calendar-page"
          onClick={() => step(-1)}
          disabled={!hasPrevious}
          aria-label="Voriger Monat"
        >
          ‹
        </button>
        <span className="calendar-title" aria-live="polite">
          {month.label}
        </span>
        <button
          type="button"
          className="calendar-page"
          onClick={() => step(1)}
          disabled={!hasNext}
          aria-label="Nächster Monat"
        >
          ›
        </button>
        <span className="calendar-total">
          {month.total === 0
            ? "kein Training"
            : `${month.total} ${month.total === 1 ? "Training" : "Trainings"}`}
        </span>
      </div>

      <table className="calendar-month">
        <caption className="calendar-sr">
          Trainings im {month.label}, nach Kalendertagen
        </caption>
        <thead>
          <tr>
            {WEEKDAYS.map((day, index) => (
              <th scope="col" key={day}>
                <abbr title={WEEKDAY_NAMES[index]}>{day}</abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {month.weeks.map((week, index) => (
            // The week has no id of its own and no meaning beyond its
            // position in the month, so its index is its key.
            <tr key={`${month.label}-${index}`}>
              {week.map((day, weekday) => (
                <td key={day ? day.date : `pad-${weekday}`}>
                  {day && (
                    <Day
                      day={day}
                      weekday={WEEKDAY_NAMES[weekday] ?? ""}
                      isToday={dayId(new Date(day.date)) === todayKey}
                      onEnter={() => setActive(day)}
                      onLeave={() => setActive(null)}
                    />
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <figcaption className="calendar-legend">
        {/* The hovered day replaces the scale rather than sitting beside it: at
            this width both together wrap onto a second line, and the scale is
            what the reader has already understood by the time they hover. */}
        {active ? (
          <span className="calendar-readout">
            {new Date(active.date).toLocaleDateString("de-DE", {
              weekday: "long", day: "numeric", month: "long",
            })}
            : {describe(active)}
          </span>
        ) : (
          <span className="calendar-legend-scale">
            <span className="calendar-key calendar-step-1" />1
            <span className="calendar-key calendar-step-2" />2
            <span className="calendar-key calendar-step-3" />3+
            <span className="calendar-legend-label">Trainings am Tag</span>
          </span>
        )}
      </figcaption>
    </figure>
  );
}

function Day({
  day,
  weekday,
  isToday,
  onEnter,
  onLeave,
}: {
  day: ActivityDay;
  weekday: string;
  isToday: boolean;
  onEnter: () => void;
  onLeave: () => void;
}) {
  const step = activityStep(day.count);
  const date = new Date(day.date);
  const spoken =
    `${weekday}, ${date.toLocaleDateString("de-DE", { day: "numeric", month: "long" })}: ` +
    describe(day);

  return (
    <span
      className={
        `calendar-day calendar-step-${step}` + (isToday ? " calendar-day-today" : "")
      }
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      {/* The day of the month on an empty day, the count on a day that has
          trainings. The number a reader is looking for differs: on an empty
          day it is "which day is this", on a full one it is "how many". */}
      <span aria-hidden="true">{day.count > 0 ? day.count : day.dayOfMonth}</span>
      {/* The full sentence for a screen reader, which cannot see that a 2 in a
          coloured cell is a count while a 2 in a plain one is a date. */}
      <span className="calendar-sr">{spoken}</span>
    </span>
  );
}

/** One day in words. Counted, never judged: a number of trainings, never a
 * verdict on them. */
function describe(day: ActivityDay): string {
  if (day.count === 0) return "kein Training";
  return `${day.count} ${day.count === 1 ? "Training" : "Trainings"}`;
}

/** A day as a key, in local time — the same construction the counts are keyed
 *  by, so "is this cell today" cannot answer differently than the shading. */
function dayId(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}
