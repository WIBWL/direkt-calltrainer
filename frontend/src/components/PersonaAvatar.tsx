import { useEffect, useState } from "react";

import { initialsOf } from "../utils/initials";

interface PersonaAvatarProps {
  /** Only ever used for the initials fallback — the picture itself is
   * decorative, see below. */
  name: string;
  /** `persona.avatar_url`, a path into the app's own static files. Null for a
   * Persona seeded without a portrait. */
  src: string | null | undefined;
  /** The shape and size, which is the surrounding screen's business: a round
   * 160px portrait in the call, a small square one on the selection card. It
   * lands on the slot element, and the picture inside it fills that slot — so
   * a slot can also crop, which the card does: at 64px a half-body shot shown
   * whole leaves a face too small to recognise. */
  className: string;
}

/**
 * A Persona's portrait, decorative (`alt=""`, the name is always beside it). A missing file falls back to the
 * initials: the database pairing and the bundled file can be out of step for a deploy (ADR 0041). The image sits
 * inside the slot so the slot can scale and shift it; the fallback takes the same slot, keeping the size.
 */
export default function PersonaAvatar({ name, src, className }: PersonaAvatarProps) {
  const [failed, setFailed] = useState(false);

  // A different Persona deserves a fresh attempt: without this, one broken
  // file would leave every later portrait in the same slot on the fallback.
  useEffect(() => setFailed(false), [src]);

  if (!src || failed) {
    return (
      <span className={`${className} persona-avatar persona-avatar-fallback`} aria-hidden="true">
        {initialsOf(name) || "?"}
      </span>
    );
  }

  return (
    <span className={`${className} persona-avatar`}>
      <img src={src} alt="" onError={() => setFailed(true)} />
    </span>
  );
}
