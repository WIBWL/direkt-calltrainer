import type { ReactNode } from "react";

import { cx } from "../utils/cx";
import AppFooter from "./AppFooter";
import AppHeader, { type TrainingStep } from "./AppHeader";

interface AppLayoutProps {
  /** Omitted outside the training flow; the header then shows no steps. */
  step?: TrainingStep;
  /** Passed through to the header — see `navigationLocked` there. */
  navigationLocked?: boolean;
  /** Marks the header's account chip as the current page. */
  accountActive?: boolean;
  /** Per-screen modifier on the page element; the shared `app-page` is added here. */
  pageClassName?: string;
  children: ReactNode;
}

/** The frame every screen shares: header, page, legal footer. Having it in one
 * place is what keeps the screens from drifting apart. */
export default function AppLayout({
  step,
  navigationLocked,
  accountActive,
  pageClassName,
  children,
}: AppLayoutProps) {
  return (
    <>
      <AppHeader
        activeStep={step}
        navigationLocked={navigationLocked}
        accountActive={accountActive}
      />

      <main className={cx("app-page", pageClassName)}>{children}</main>

      <AppFooter />
    </>
  );
}
