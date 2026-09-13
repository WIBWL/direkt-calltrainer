# ADR 0089: The Closing Is Read as Three Parts, in the User's Last Two Turns

## Status

Accepted. Introduces the `closing` metric (Gesprächsabschluss, F-65) and gives the focus goal "Klarer Gesprächsabschluss" its first measurement, which moves its `focus_goal.evidence` from `interpretive` to `mixed`. The counterpart of ADR 0086 at the other end of the call, and written against it: where that one differs by who rang, this one does not.

## Context

The catalogue text for the goal is as specific as the opening's: "Ein guter Abschluss sichert Verbindlichkeit. Er fasst kurz zusammen, hält eine klare Vereinbarung fest und verabschiedet freundlich. Offene oder abrupte Enden hinterlassen Unsicherheit." Three parts, named in the text the user picked the goal by.

Until now the goal was one of the four with no measurement at all (ADR 0080, docs/dashboard-konzept.md section 4.2). What it had was the wrap-up's prose and F-42's phase paragraph — which says whether the *register* moved with the phase of the call, not whether anything was settled at its end.

Unlike the articulation, which stays unmeasured on purpose (three independent reasons, section 4.2), nothing about the closing is out of reach: whether a recap was given and a next step named is in the words, and the words are stored.

## Decision

**The user's last two turns are checked for three parts: a recap of what was settled, a concrete next step, and a farewell.**

Each is a pattern in the Session's `LanguagePack` (ADR 0083), German and English:

- **Zusammenfassung** — `recap_re`: "ich fasse zusammen", "zusammengefasst", "halten wir fest", "wir haben vereinbart / besprochen / festgehalten".
- **Vereinbarung** — `agreement_re`: a first-person action ("ich schicke Ihnen", "ich melde mich bis Montag"), what the other side will get ("Sie bekommen bis morgen"), the words that settle it ("so verbleiben wir", "abgemacht", "nächster Schritt") or a deadline ("bis Freitag"). Deliberately **not** "ich kümmere mich darum": that is the vague reassurance the Persona's own prompt is warned about (`vague_reassurance_examples`), and it commits to nothing a caller could hold anyone to.
- **Verabschiedung** — `sign_off_re`: "auf Wiederhören", "tschüss", "schönen Tag", "danke für Ihren Anruf". Wider than the live path's `farewell_re`, which is left untouched: that one decides mid-call whether the call is over, where a false match cuts a conversation short, and "einen schönen Tag noch" is a farewell here without being a request to hang up.

The value is how many parts were recognised, so the unit is "von 3", as for the opening.

### The window is the last two turns

Two, not one: a recap or the agreed next step usually comes a turn before the goodbye, with the Persona's answer in between, and the last turn on its own is often only "Danke, auf Wiederhören". Not three: at the six to nine turns these calls actually run to, three turns is a third of the call, and a "bis Freitag" from the middle of a negotiation would pass for a closing agreement.

Below **three** user turns the metric is absent rather than zero — the window would otherwise reach back into the opening, and a call hung up after a sentence or two has no end of its own. That is the same floor at which the post-call screen stops offering a follow-up and a reverse (`MIN_USER_TURNS`), for the same reason.

### The same parts whoever rang

ADR 0086 splits the opening's third part by who called, because the called side offers help where the caller states a concern. Nothing similar applies here: ending a call well asks the same of both sides, so a reverse (ADR 0070) is measured exactly like an ordinary call. `conversation()` already carries `reverse`; this deriver ignores it.

### The tile shows the parts, not the count

As for the opening, and now from one shared list (`utils/metrics.ts`): the tile, the progress view and the downloadable report all read `metricParts`, so a new checklist metric cannot be a checklist on one screen and a climbing line on another. "2" in display type is the mark ADR 0086 kept off the screen, and the PDF used to print exactly that for the opening — it now names the parts in words there too, the fonts carrying no check mark.

"Nicht erkannt", never "fehlt". A recap worded some other way slips past the patterns, and the tile says what the check did rather than what the user did. The stored detail carries `turns_read`, so the screen can say where it looked with the backend's own number (ADR 0063's pattern) rather than a copy of it.

### What is measured and what is not

The parts are counted; whether the close was *clear* is not. Whether the right things were summed up, and whether the next step is one the other side will actually take, stays the wrap-up's to say — which is why the goal's evidence is `mixed` and not `measured`, and why nothing here carries a threshold, a colour or a target (ADR 0004, ADR 0051, ADR 0078).

## Consequences

The goal is backed in the progress view by this metric, drawn as one mark per training with the count of recognised parts (`PartsStrip`), not as a line over a band: it is F-63's series shape, for F-63's reason.

The patterns will miss real closings, and they were written from how German and English service calls usually end rather than tested against a corpus. Every miss shows as "nicht erkannt".

Because the parts come from words alone, they **can** be computed for Sessions stored earlier — `scripts/backfill_closing.py [--apply]`, the third metric that reaches backwards after F-51's interruptions and F-53's run length. ADR 0048 does not bite: nothing here needs the recording. A backfilled row carries `backfilled: true`, as the run-length one does.

The wrap-up's dossier gains one line ("Gesprächsabschluss: 2.0 von 3"), like every other Measurement. It is a fact handed to the model, not an instruction: the prompt's rule against judging a figure against a norm is unchanged (ADR 0049, ADR 0051).
