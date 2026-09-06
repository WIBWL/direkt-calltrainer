import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import AppLayout from "./AppLayout";

/**
 * The frame the three legal pages share: imprint, privacy statement and
 * accessibility statement.
 *
 * They are long documents rather than screens, so they get a reading width and
 * no training step in the header. The way back goes to the training rather
 * than to the previous page: someone who arrived here from the footer of a
 * wrap-up should not be sent back into a call they have finished.
 */
export default function LegalPage({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <AppLayout pageClassName="app-page-narrow legal-page">
      <Link to={ROUTES.training} className="back-link">
        Zurück zum Training
      </Link>
      <h1>{title}</h1>
      {children}
    </AppLayout>
  );
}
