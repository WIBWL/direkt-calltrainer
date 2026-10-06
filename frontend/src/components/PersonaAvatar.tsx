import { useEffect, useState } from "react";

import { initialsOf } from "../utils/initials";

interface PersonaAvatarProps {
  /** For the initials fallback. */
  name: string;
  /** Null without a portrait. */
  src: string | null | undefined;
  /** On the slot, which the picture fills, so a slot can crop (the card does). */
  className: string;
}

/** Decorative (`alt=""`): the name is always beside it. A missing file falls back to the initials (ADR 0041). */
export default function PersonaAvatar({ name, src, className }: PersonaAvatarProps) {
  const [failed, setFailed] = useState(false);

  // A new Persona gets a fresh attempt.
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
