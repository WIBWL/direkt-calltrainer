# ADR 0086: The Opening Turn Is Read as Three Parts, Depending on Who Rang

## Status

Accepted. Introduces the `opening` metric (Gesprächseinstieg, F-63) and gives the focus goal "Souveräner Gesprächseinstieg" its first measurement — ADR 0080 still lists it among the goals without one, which this supersedes. `Conversation` carries the user's turns one by one and whether the Session was a reverse (ADR 0070).

## Context

The catalogue text for the goal is specific: "Gefragt ist ein Einstieg, der Name, Anliegen und Rahmen vermittelt, ohne zu hetzen. Dabei zählt beides: Wie ruhig und zugewandt Sie klingen und ob inhaltlich nichts fehlt." Two halves, then — whether the parts are there, and how the turn was delivered.

Who opens decides what the parts are. In an ordinary Session the Persona calls and speaks first, with a greeting, its name and the reason for its call (`opening_instruction` in `session/prompting.py`); the user answers as the one who was called. In a reverse the Persona picks up and says only how someone answers a phone, and the user is the caller. The first thing the user says is therefore the answer of the called side in one case and the opening of the caller in the other.

A name cannot be looked for directly, because it is not known.

## Decision

**The user's first turn is checked for three parts — a greeting, their own name, and a third part that depends on who rang — and its tempo is set against the rest of their own call.**

### The three parts

Each is a pattern in the Session's `LanguagePack` (ADR 0083):

- **Begrüßung** — "guten Tag", "hallo", "grüß Gott", "moin" …
- **Name** — found by the frames it is said in, followed by a capitalised word: "mein Name ist …", "hier ist …", "… am Apparat"; in English also "I'm …". The capital is what separates "hier ist Schmidt" from "hier ist alles", and a negative lookahead keeps "hier ist Ihr Ansprechpartner" out. German has no safe "ich bin …": nouns are capitalised, and "ich bin Kunde" would pass for a name.
- **Hilfsangebot** when the user was called (`offer_re`: "Was kann ich für Sie tun?", "Wie kann ich Ihnen helfen?", "Worum geht es?") — the caller has already said what they want, so what is asked of the called side is to offer help, not to state a concern. **Anliegen** when the user rang (`concern_re`: "Ich rufe an wegen …", "Es geht um …"). The two patterns are kept apart: "Ich rufe an wegen" is no offer of help, and "Was kann ich für Sie tun?" is no concern. The first version put both in one pattern under the one label "Anliegen", which was wrong for every ordinary call.

`persistence.py` passes `scenario.reverse` into `conversation()`, and the detail stores the third part under its own key (`offer` or `concern`), so the screen names the part that was actually checked. Calls stored before the split carry `concern`.

The value is how many parts were recognised, so the unit is "von 3".

### The tile shows the parts, not the count

The first version led the tile with the count. In the first test it read **"1 von 3"**, and the user asked what that meant — it was not self-explanatory, and it read like a mark, which is what this application avoids everywhere (ADR 0004). The tile now shows the three parts, each marked (✓ said, – not recognised), and the count stays in the stored value only.

"Not recognised", never "missing": a bare name ("Schmidt, guten Tag") slips past the frames, so the absence of a match is not proof of an absence. That is also what a screen reader hears. The marks carry no colour; which part was said is a fact, and colour in this application says something about a value (ADR 0078).

### The tempo is read against the user themselves

The opening turn's words per phonated minute over those of the rest of the user's turns, shown as "Einstieg 20 % schneller als sonst". The reference is the same speaker in the same call, so no norm is invented (ADR 0051). It is left out when the first turn has fewer than four words, the rest fewer than fifteen, or the recording has no detectable silence (ADR 0085), since phonation time is what it divides by.

## Consequences

The goal is backed in the progress view by this metric. There the value is still plotted as 0 to 3 over time; as a course it reads less like a mark than on a single tile, but it is the same number, and a display that shows the parts over time would be more faithful.

The patterns will miss real openings — names without a frame, an offer phrased some other way. They were tested against one real call so far, in English; the German ones are written from how German service calls usually open. Every miss is shown as "nicht erkannt", which says what the check did rather than what the user did.

The parts can be recomputed for stored Sessions from their transcripts. The tempo can too for Sessions stored since ADR 0081, which keeps each utterance's phonation time in `turn.acoustics_json`; for earlier ones it cannot.
