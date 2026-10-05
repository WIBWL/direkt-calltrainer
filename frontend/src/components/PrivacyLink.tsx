import { PRIVACY_URL } from "../routes";
import ProjectPageLink from "./ProjectPageLink";

/** The link to the privacy statement, the project's own page. Its own
 *  component because five places name it, and the target must not drift
 *  between them. */
export default function PrivacyLink({ children }: { children: string }) {
  return <ProjectPageLink href={PRIVACY_URL}>{children}</ProjectPageLink>;
}
