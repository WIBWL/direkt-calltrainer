import { useLayoutEffect, useRef, useState } from "react";

export interface FilterOption<T extends string> {
  value: T;
  label: string;
  /** How many Scenarios this option would show. */
  count: number;
}

interface FilterSliderProps<T extends string> {
  options: FilterOption<T>[];
  value: T;
  onChange: (next: T) => void;
  label: string;
}

/**
 * One row of the Scenario library filter: a track, one option per value, and a
 * thumb that slides onto whichever is active.
 *
 * Used for both levels (origin above, thematic category below), which is what
 * keeps them the same size: one component, one stylesheet, so the second row
 * cannot end up smaller than the first by drifting apart.
 *
 * A `radiogroup` rather than an `input type="range"`, because the options are
 * nominal. Dragging along an axis would imply an order between "Support" and
 * "Angebot & Preis" that does not exist, and a range input announces itself to
 * a screen reader as a number. Arrow keys move the selection, which is what a
 * radiogroup gives for free and what makes it behave like a slider on the
 * keyboard too.
 */
export default function FilterSlider<T extends string>({
  options,
  value,
  onChange,
  label,
}: FilterSliderProps<T>) {
  const trackRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef(new Map<T, HTMLButtonElement>());
  // Pixel geometry of the active option, measured rather than computed: the
  // labels have different widths, so equal-width thumbs would sit off-centre.
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);

  useLayoutEffect(() => {
    const measure = () => {
      const track = trackRef.current;
      const active = optionRefs.current.get(value);
      if (!track || !active) return;
      setThumb({
        left: active.offsetLeft - track.clientLeft,
        width: active.offsetWidth,
      });
    };
    measure();
    // The labels reflow on resize and when the font finally loads, and the
    // thumb is positioned in pixels, so it has to be re-measured then.
    const observer = new ResizeObserver(measure);
    if (trackRef.current) observer.observe(trackRef.current);
    return () => observer.disconnect();
  }, [value, options]);

  // Wraps at both ends, so the row can be cycled without reaching for the other
  // arrow key. `value` is always one of the options, so the index is never -1.
  const move = (delta: number) => {
    const index = options.findIndex((o) => o.value === value);
    const wrapped = (index + delta + options.length) % options.length;
    const next = options[wrapped];
    if (!next) return;
    onChange(next.value);
    optionRefs.current.get(next.value)?.focus();
  };

  return (
    <div className="filter-slider" role="radiogroup" aria-label={label} ref={trackRef}>
      {/* Decorative: the selection it marks is announced by aria-checked. */}
      <span
        className={"filter-slider-thumb" + (thumb ? "" : " is-unmeasured")}
        style={thumb ? { transform: `translateX(${thumb.left}px)`, width: thumb.width } : undefined}
        aria-hidden="true"
      />
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          // Roving tabindex: the row is one tab stop, arrows move inside it.
          tabIndex={value === option.value ? 0 : -1}
          ref={(el) => {
            if (el) optionRefs.current.set(option.value, el);
            else optionRefs.current.delete(option.value);
          }}
          className={"filter-slider-option" + (value === option.value ? " active" : "")}
          onClick={() => onChange(option.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowDown") {
              e.preventDefault();
              move(1);
            } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
              e.preventDefault();
              move(-1);
            }
          }}
        >
          {option.label}
          <span className="filter-slider-count">{option.count}</span>
        </button>
      ))}
    </div>
  );
}
