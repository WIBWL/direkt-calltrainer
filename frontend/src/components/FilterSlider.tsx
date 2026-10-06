import { useLayoutEffect, useRef, useState } from "react";

export interface FilterOption<T extends string> {
  value: T;
  label: string;
  count: number;
}

interface FilterSliderProps<T extends string> {
  options: FilterOption<T>[];
  value: T;
  onChange: (next: T) => void;
  label: string;
}

/** One filter row. A `radiogroup`, not a range: the options are nominal. */
export default function FilterSlider<T extends string>({
  options,
  value,
  onChange,
  label,
}: FilterSliderProps<T>) {
  const trackRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef(new Map<T, HTMLButtonElement>());
  // Measured: the labels differ in width.
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
    // Re-measured on reflow and font load.
    const observer = new ResizeObserver(measure);
    if (trackRef.current) observer.observe(trackRef.current);
    return () => observer.disconnect();
  }, [value, options]);

  // Wraps at both ends.
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
          // Roving tabindex.
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
