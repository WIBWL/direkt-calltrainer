import { PRIVACY_URL } from "../routes";
import ProjectPageLink from "./ProjectPageLink";

/** One component, so the target cannot drift between its five uses. */
export default function PrivacyLink({ children }: { children: string }) {
  return <ProjectPageLink href={PRIVACY_URL}>{children}</ProjectPageLink>;
}
