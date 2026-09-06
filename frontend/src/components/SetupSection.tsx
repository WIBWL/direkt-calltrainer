import type { ReactNode } from "react";

// These properties describe one numbered section on the setup page.
interface SetupSectionProps {
  index: string;
  title: string;
  description: string;
  children: ReactNode;
}

export default function SetupSection({
  index,
  title,
  description,
  children,
}: SetupSectionProps) {
  // Each section needs a unique ID to connect its heading with the section.
  const headingId = `setup-section-${index}`;

  return (
    <section className="setup-section" aria-labelledby={headingId}>
      {/* The heading displays the section number, title and short instruction. */}
      <div className="setup-section-heading">
        <span className="setup-section-index" aria-hidden="true">
          {index}
        </span>

        <div className="setup-section-heading-text">
          <h2 id={headingId}>{title}</h2>
          <p>{description}</p>
        </div>
      </div>

      {/* The parent page provides the individual content for each section. */}
      <div className="setup-section-content">{children}</div>
    </section>
  );
}
