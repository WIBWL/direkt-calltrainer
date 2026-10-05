/** A link to one of the EFRE DiReKT project's own pages (imprint, privacy
 *  statement, accessibility statement), which this application does not carry.
 *  A new tab, because the way out of a finished wrap-up must not discard it.
 *  One component for every such link, the reason `BrandName` is one — a second
 *  copy is where the new-tab hint would drift. `children` is the wording each
 *  sentence needs, and typing it as a string is what lets the accessible name
 *  contain the visible text (WCAG 2.5.3) while the hint still gets said. */
export default function ProjectPageLink({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${children} (öffnet in neuem Tab)`}>
      {children}
    </a>
  );
}
