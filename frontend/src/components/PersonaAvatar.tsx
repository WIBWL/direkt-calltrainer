import { useEffect, useState } from "react";

interface PersonaAvatarProps {
  /** Only ever used for the initials fallback — the picture itself is
   * decorative, see below. */
  name: string;
  /** `persona.avatar_url`, a path into the app's own static files. Null for a
   * Persona seeded without a portrait. */
  src: string | null | undefined;
  /** The shape and size, which is the surrounding screen's business: a round
   * 160px portrait in the call, a wide banner on the selection card. */
  className: string;
}

/** Initials for the fallback, limited to the first two name parts. */
export function getInitials(name: string): string {
  const initials = name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  return initials || "?";
}

/**
 * A Persona's portrait, with its initials as the fallback.
 *
 * Decorative everywhere it is used (`alt=""`): the card, the info panel and the
 * call screen all name the Persona in text right beside the picture, so a
 * screen reader that read the image too would say the name twice. It carries
 * no information the text does not.
 *
 * A missing file falls back to the initials rather than to a broken image. The
 * pairing lives in the database and the file in the frontend bundle (ADR 0041
 * keeps Persona content in the table), so the two can be out of step for one
 * deploy — and a Persona with no picture is fully playable either way.
 */
export default function PersonaAvatar({ name, src, className }: PersonaAvatarProps) {
  const [failed, setFailed] = useState(false);

  // A different Persona deserves a fresh attempt: without this, one broken
  // file would leave every later portrait in the same slot on the fallback.
  useEffect(() => setFailed(false), [src]);

  if (!src || failed) {
    return (
      <span className={`${className} persona-avatar-fallback`} aria-hidden="true">
        {getInitials(name)}
      </span>
    );
  }

  return (
    <img className={className} src={src} alt="" onError={() => setFailed(true)} />
  );
}
