# ADR 0086: The Opening Turn Is Read as Three Parts, Depending on Who Rang

## Context

"Souveräner Gesprächseinstieg" asks for name, concern and framing without rushing. What the first turn should contain depends on who rang: the called side offers help, the caller states a concern.

## Decision

- The user's first turn is checked for a **greeting**, their **name** (found by its frame plus a capitalised word, so "hier ist Schmidt" counts and "hier ist alles" does not), and an **offer** of help when called or a **concern** when the user rang (a reverse). The patterns are per language pack, and the third part is stored under its own key.
- The value is the number of parts found, "von 3". The tile shows the three parts marked ✓ or "nicht erkannt", never "fehlt", with no colour.
- Tempo: the first turn's words per phonated minute over the rest of the user's call, omitted below four or fifteen words or without detectable silence.

## Consequences

The patterns will miss real openings, and every miss reads "nicht erkannt". The progress view plots 0–3 over time, which reads more like a mark than the tile does.
