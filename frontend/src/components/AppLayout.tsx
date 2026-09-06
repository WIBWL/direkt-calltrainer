import type { ReactNode } from "react";

import { cx } from "../utils/cx";
import AppFooter from "./AppFooter";
import AppHeader, { type TrainingStep } from "./AppHeader";

interface AppLayoutProps {
  step: TrainingStep;
  /** Per-screen modifier on the page element; the shared `app-page` is added here. */
  pageClassName?: string;
  children: ReactNode;
}

/** The frame every screen shares: progress header, page, legal footer. Having
 * it in one place is what keeps the three of them from drifting apart. */
export default function AppLayout({ step, pageClassName, children }: AppLayoutProps) {
  return (
    <>
      <AppHeader activeStep={step} />

      <main className={cx("app-page", pageClassName)}>{children}</main>

      <AppFooter />
    </>
  );
}
