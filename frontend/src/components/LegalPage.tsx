import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { ROUTES } from "../routes";
import AppLayout from "./AppLayout";

/**
 * The frame the three legal pages share: a reading width, no training step. The way back
 * goes to the training, not the previous page, so nobody is sent back into a finished call.
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
