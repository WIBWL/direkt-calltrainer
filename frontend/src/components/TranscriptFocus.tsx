import { createContext, useContext, type ReactNode } from "react";

/**
 * Showing the reader the line a sentence of the wrap-up is about.
 *
 * Every strength and every improvement point carries the Turn it was written
 * about (`feedback_point.turn_id`), and the screen has printed that moment as a
 * timestamp since the points existed. A timestamp is not something a reader can
 * act on: "2:48" is checkable only by somebody who remembers the call, which is
 * nobody a minute after it ended. The transcript holding that very line sits
 * three inches below, collapsed.
 *
 * So the timestamp becomes a control, and this is the wire between the two
 * halves. It is a context and not a prop because the two are not neighbours:
 * `FeedbackScreen` owns the transcript and takes the report as a finished
 * element, so there is nothing to hand a callback down through.
 *
 * **Null means there is no transcript on this screen**, and a point then renders
 * its timestamp as the plain text it always was. That is a real case rather
 * than a defensive one: `FeedbackReport` is also drawn into the downloadable
 * report and could be drawn anywhere else, and a button that does nothing is
 * worse than no button.
 */
export interface TranscriptFocus {
  /** Open the transcript and bring the line spoken at this offset into view. */
  reveal: (offsetMs: number) => void;
  /** The line currently pointed at, so it can be marked while it is read. */
  focused: number | null;
}

const Context = createContext<TranscriptFocus | null>(null);

export function TranscriptFocusProvider({
  value,
  children,
}: {
  value: TranscriptFocus;
  children: ReactNode;
}) {
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

/** The transcript on this screen, or null where there is none. */
export function useTranscriptFocus(): TranscriptFocus | null {
  return useContext(Context);
}
