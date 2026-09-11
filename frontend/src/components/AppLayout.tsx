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
  /** Marks the header's progress link as the current page. */
  progressActive?: boolean;
  /** Widens the header to the same measure as a wide page, so brand and account
   *  chip line up with the content instead of sitting inside it. */
  wide?: boolean;
  /** Passed through to the header — see `onHome` there. */
  onHome?: () => void;
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
  progressActive,
  wide,
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
        wide={wide}
        onHome={onHome}
      />

      <main className={cx("app-page", pageClassName)}>{children}</main>

      <AppFooter />
    </>
  );
}
