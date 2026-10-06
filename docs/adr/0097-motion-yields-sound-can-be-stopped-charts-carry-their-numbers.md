# ADR 0097: Motion Yields to the System Setting, Sound Can Be Stopped, Charts Carry Their Numbers in Text

## Context

The frontend has things that move, ring and draw. Without a rule, each new animation would be decided differently.

## Decision

- **Motion:** `prefers-reduced-motion` is read at the moment it matters. Under it:
  - an animation that is the whole screen is skipped together with the screen (the die);
  - an animation covering a change is skipped and the change still happens (the fade);
  - a waiting or decision screen stays, standing still (the ringing phone);
  - decorative transitions are switched off in CSS.
- **Sound:** the only self-starting sound is the synthesized ringtone. It can be stopped with an on-screen switch, remembered per browser. Without an AudioContext it is silent.
- **Charts** are inline SVG with no library. Each is `role="img"`, with its numbers in the accessible name. Where values are the point, a real table carries them. Colour is never the only channel.
- **The live call's state is not narrated** to screen readers; the Persona's voice is the signal.

## Consequences

A new animation must declare which kind it is. Chart data appears twice. Nothing is checked automatically, and the BITV self-assessment is outstanding.
