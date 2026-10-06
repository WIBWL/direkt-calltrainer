import { createContext, useContext, type ReactNode } from "react";

/** Lets a point's timestamp open the transcript at its line. Null = no transcript
 * on this screen: the timestamp stays plain text. */
export interface TranscriptFocus {
  reveal: (offsetMs: number) => void;
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

export function useTranscriptFocus(): TranscriptFocus | null {
  return useContext(Context);
}
