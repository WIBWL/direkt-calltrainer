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

/** When the user trained, a month at a time (F-13), outside the period switch.
 * Counting implies no norm (ADR 0065). A real `<table>`, for screen readers. */

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
  // Separate from the hover readout, or hovering would close an opened list.
  const [opened, setOpened] = useState<string | null>(null);

  const month = useMemo(
    () => activityMonth(sessions, shown.year, shown.month),
    [sessions, shown.year, shown.month],
  );
  const earliest = useMemo(() => firstTrainingMonth(sessions), [sessions]);

  const at = shown.year * 12 + shown.month;
  const hasPrevious = earliest !== null && at > earliest.year * 12 + earliest.month;
  const hasNext = at < today.getFullYear() * 12 + today.getMonth();
  const todayKey = dayKey(today);

  const step = (by: number) => {
    // Readout and list belong to the month being left.
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
        {/* Replaces the scale: both together wrap. */}
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

      {/* Under the calendar, so the month does not change shape. */}
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

  // The date on an empty day, the count on a full one; the sentence for screen readers.
  const content = (
    <>
      <span aria-hidden="true">{day.count > 0 ? day.count : day.dayOfMonth}</span>
      <span className="calendar-sr">{spoken}</span>
    </>
  );

  // An empty day is no button: thirty tab stops to reach two.
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

function describe(day: ActivityDay): string {
  if (day.count === 0) return "kein Training";
  return `${day.count} ${day.count === 1 ? "Training" : "Trainings"}`;
}
