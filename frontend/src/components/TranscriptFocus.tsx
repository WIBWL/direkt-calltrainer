import { createContext, useContext, type ReactNode } from "react";

/**
 * Lets a wrap-up point's timestamp (`feedback_point.turn_id`) open the transcript at that line; a context because
 * `FeedbackScreen` owns the transcript and takes the report finished. **Null = no transcript on this screen**
 * (e.g. the downloadable report): the timestamp stays plain text rather than a button that does nothing.
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
