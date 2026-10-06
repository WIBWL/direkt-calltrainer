import type { ReactNode } from "react";

import { cx } from "../utils/cx";
import AppFooter from "./AppFooter";
import AppHeader, { type TrainingStep } from "./AppHeader";

interface AppLayoutProps {
  step?: TrainingStep;
  /** See `navigationLocked` in AppHeader. */
  navigationLocked?: boolean;
  accountActive?: boolean;
  progressActive?: boolean;
  /** See `onHome` in AppHeader. */
  onHome?: () => void;
  pageClassName?: string;
  children: ReactNode;
}

/** The frame every screen shares: header, page, footer. */
export default function AppLayout({
  step,
  navigationLocked,
  accountActive,
  progressActive,
  onHome,
  pageClassName,
  children,
}: AppLayoutProps) {
  return (
    <>
      <AppHeader
        activeStep={step}
        navigationLocked={navigationLocked}
        accountActive={accountActive}
        progressActive={progressActive}
        onHome={onHome}
      />

      <main className={cx("app-page", pageClassName)}>{children}</main>

      <AppFooter />
    </>
  );
}
