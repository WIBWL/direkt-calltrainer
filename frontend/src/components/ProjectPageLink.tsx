/** One of the DiReKT project's own pages, in a new tab so a finished wrap-up is not
 * discarded. `children` is a string, so the accessible name contains it (WCAG 2.5.3). */
export default function ProjectPageLink({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`${children} (öffnet in neuem Tab)`}>
      {children}
    </a>
  );
}
