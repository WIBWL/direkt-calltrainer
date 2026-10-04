import { PRIVACY_URL } from "../routes";

/** The link to the privacy statement, which is not in this application: the
 *  project's own page carries it, so every mention points straight there rather
 *  than through a page of ours. One component for all five places, the reason
 *  `BrandName` is one — a second copy is where the target or the new-tab hint
 *  would drift. `children` is the wording each sentence needs, and typing it as
 *  a string is what lets the accessible name contain the visible text
 *  (WCAG 2.5.3) while the hint still gets said. */
export default function PrivacyLink({ children }: { children: string }) {
  return (
    <a
      href={PRIVACY_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`${children} (öffnet in neuem Tab)`}
    >
      {children}
    </a>
  );
}
