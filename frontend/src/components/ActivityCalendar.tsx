import { useMemo, useState } from "react";

import type { SessionSummary } from "../protocol";
import {
  activityMonth,
  activityStep,
  dayKey,
  firstTrainingMonth,
  trainingsOn,
  type ActivityDay,
} from "../utils/progressStats";
import TrainingLinks from "./TrainingLinks";

/**
 * When the user trained, one month at a time (F-13). The period switch deliberately does
 * not reach it: the grid carries its own range. Counting implies no norm (ADR 0065), and
 * the printed count makes the shading redundant. A real `<table>` for screen readers.
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
  // The day whose trainings are listed under the calendar. Separate from
  // `active`, which is the hover readout: pointing at a cell and opening one
  // are two different acts, and letting a hover close an opened list would
  // make the list impossible to reach with the mouse still on the grid.
  const [opened, setOpened] = useState<string | null>(null);

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
  const todayKey = dayKey(today);

  const step = (by: number) => {
    // The readout names a day of the month on screen; paging away from it would
    // otherwise leave that sentence standing over a different month. The same
    // goes for an opened day's list, which would then sit under a month it does
    // not belong to.
    setActive(null);
    setOpened(null);
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
                      isToday={dayKey(new Date(day.date)) === todayKey}
                      isOpen={opened === day.date}
                      onEnter={() => setActive(day)}
                      onLeave={() => setActive(null)}
                      onOpen={() =>
                        setOpened((current) => (current === day.date ? null : day.date))
                      }
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

      {/* Under the whole calendar rather than under the week that was pressed:
          a row inserted into the grid would push the following weeks down and
          make the month change shape as it is read. */}
      {opened && (
        <TrainingLinks
          title={`Trainings am ${new Date(opened).toLocaleDateString("de-DE", {
            day: "numeric",
            month: "long",
          })}`}
          sessions={trainingsOn(sessions, new Date(opened))}
        />
      )}
    </figure>
  );
}

function Day({
  day,
  weekday,
  isToday,
  isOpen,
  onEnter,
  onLeave,
  onOpen,
}: {
  day: ActivityDay;
  weekday: string;
  isToday: boolean;
  isOpen: boolean;
  onEnter: () => void;
  onLeave: () => void;
  onOpen: () => void;
}) {
  const step = activityStep(day.count);
  const date = new Date(day.date);
  const spoken =
    `${weekday}, ${date.toLocaleDateString("de-DE", { day: "numeric", month: "long" })}: ` +
    describe(day);

  const className =
    `calendar-day calendar-step-${step}` +
    (isToday ? " calendar-day-today" : "") +
    (isOpen ? " calendar-day-open" : "");

  // The day of the month on an empty day, the count on a day that has
  // trainings. The number a reader is looking for differs: on an empty day it
  // is "which day is this", on a full one it is "how many". The full sentence
  // goes to a screen reader, which cannot see that a 2 in a coloured cell is a
  // count while a 2 in a plain one is a date.
  const content = (
    <>
      <span aria-hidden="true">{day.count > 0 ? day.count : day.dayOfMonth}</span>
      <span className="calendar-sr">{spoken}</span>
    </>
  );

  // A day with nothing on it stays a plain cell. Making every cell a button
  // would put thirty stops in the tab order to reach the two that open
  // something, and a control that does nothing when pressed is worse than no
  // control.
  if (day.count === 0) {
    return (
      <span className={className} onMouseEnter={onEnter} onMouseLeave={onLeave}>
        {content}
      </span>
    );
  }

  return (
    <button
      type="button"
      className={className}
      aria-expanded={isOpen}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onClick={onOpen}
    >
      {content}
    </button>
  );
}

/** One day in words. Counted, never judged: a number of trainings, never a
 * verdict on them. */
function describe(day: ActivityDay): string {
  if (day.count === 0) return "kein Training";
  return `${day.count} ${day.count === 1 ? "Training" : "Trainings"}`;
}
