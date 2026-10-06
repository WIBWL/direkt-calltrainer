import type { ReactNode } from "react";

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
  const headingId = `setup-section-${index}`;

  return (
    <section className="setup-section" aria-labelledby={headingId}>
      <div className="setup-section-heading">
        <span className="setup-section-index" aria-hidden="true">
          {index}
        </span>

        <div className="setup-section-heading-text">
          <h2 id={headingId}>{title}</h2>
          <p>{description}</p>
        </div>
      </div>

      <div className="setup-section-content">{children}</div>
    </section>
  );
}
