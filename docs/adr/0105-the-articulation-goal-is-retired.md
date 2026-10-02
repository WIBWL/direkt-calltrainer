# ADR 0105: "Deutliche Artikulation" Is Retired from the Focus Catalogue

## Status

Accepted. Removes the focus goal `articulation` from `seed_data.FOCUS_GOALS`, leaving thirteen in four groups. Amends ADR 0076, which introduced the catalogue at fourteen, and answers the open question `docs/dashboard-concept.md` section 4.2 put to the project lead. The second goal to go this way; ADR 0076's first amendment retired "Souveräne Lautstärke" on a narrower version of the same argument.

It does **not** change F-38 or ADR 0084. Articulation stays in the feature list as a requirement this application answers with a reasoned no, and ADR 0084 remains where the reasons for that no are recorded. What goes is the offer to train it as a focus.

## Context

A focus goal is a promise. The User picks at most five from the catalogue, at first start and again in the profile, and every screen after that is arranged around what they picked: the top block of the progress view, the goal's own second-level page, the practice suggestion, and the tag the wrap-up puts on each of its points (ADR 0080). Picking a goal spends one of five slots and directs the application's attention.

`articulation` could not answer that promise, and had stopped claiming it could. Its `focus_goal.evidence` was moved from `mixed` to `interpretive` when section 4.2 of the dashboard concept was written, on the ground that "gemischt" was a promise of a measurement that is not coming. Its tile said, in so many words, that there is no measurement and none is planned. Its entry in `focusMetrics.ts` carried a note of its own for exactly that sentence.

So the goal was already the odd one out. What section 4.2 asked was whether a goal in that state should stay on offer at all, and it declined to decide alone.

### Why no measurement is coming

Three reasons, each sufficient on its own.

**The microphone cannot be factored out.** Indistinctness shows in the spectral sharpness of the signal, and that depends on the microphone, the distance to it and the browser's automatic gain as much as on the speaker. This is the argument that retired the loudness goal, and it bites harder here. The loudness kept one valid reading after that retirement: inside a single call the comparison of two stretches holds, because the device is the same on both sides (ADR 0081), which is why the `loudness` metric survived while its goal did not. A figure for distinctness has no such internal reference point. There is nothing left over to keep.

**The recogniser tidies up before anything could measure.** Whisper normalises swallowed endings into correct words, exactly as it normalises the hesitation sounds away (ADR 0084). Indistinctness is therefore not readable from the transcript, and measuring the word error rate would report the quality of the recogniser.

**There would be no threshold.** Even with a clean measure it would stay open at what point somebody speaks indistinctly. Nothing is validated for this population, and ADR 0051 forbids the invention precisely here.

### The one signal that looked usable, and why it is not

The obvious remaining idea is to count the other side asking back: "Wie bitte?", "Können Sie das wiederholen?", as a pattern over the Persona's turns in the `LanguagePack`, the way `filler_re` counts lexical fillers (ADR 0083). It was considered and rejected.

The Persona never mishears. It reads a transcript, and where that transcript is garbled it is Whisper's reading of the audio that failed, not a listener. So the signal is mediated by the recogniser's quality and, on top of that, by whether the model chooses to ask back at all, which the system prompt discourages: it is told to keep the call moving. What would be reported is a property of the pipeline wearing the User's name. That is the same defect ADR 0051 names when it rules out measuring anything against the Persona.

### What was weighed against removal

Distinctness is a real skill in telephone work, and the application is now silent about it. Locke & Latham (2002) is the honest argument for keeping the goal anyway: a specific goal has an effect through attention alone, before any feedback arrives. Somebody who picks "Deutliche Artikulation" thinks about it while speaking, and this application would have cost them nothing to let them.

That is real and it is outweighed. The cost is not nothing: the slot is one of five, and what the User receives for it is a tile stating that nothing here is measured and nothing will be. Offering a goal the application will never be able to say anything about is the same kind of promise the loudness goal was retired for, one step worse, because the loudness at least kept a reading inside a call.

The two remaining text-only goals are **not** in the same position, and the asymmetry is what decides this. Whether an objection was handled and whether somebody sounded like they cared are things that live in what was said, and what was said is stored and read by the wrap-up. For the articulation, what the goal is about is exactly what the transcript does not carry. Section 4.2 already recorded that its wrap-up text is the thinnest of the three; this ADR draws the line there.

## Decision

**The `articulation` entry is removed from `seed_data.FOCUS_GOALS`.**

Everything else follows from that one edit, because every reader derives from the list:

- `provision._deactivate_missing` sets the row's `active` to false rather than deleting it. `focus_selection_goal` rows and `feedback_point.focus_goal_id` reference it, and a past statement does not become untrue because a goal left the catalogue.
- `api/focus.py` already drops a retired key from the *served* selection, so an existing pick stops holding one of the five slots and no card appears for it. That mechanism was built for the loudness retirement and needed no change.
- `generator._goal_catalogue` builds the prompt's vocabulary from the same list, so the wrap-up is no longer shown the key and cannot assign it. `_goal_ids` keeps deactivated goals on purpose, so the tags already written still resolve.
- `focusMetrics.FOCUS_BACKING` and `practiceRoutes.PRACTICE_CATEGORY` lose their entries. A key the catalogue no longer names falls to `backingOf`'s honest fallback, and a goal absent from `PRACTICE_CATEGORY` yields no practice suggestion rather than a random one.

The eleven goals that stood after it are renumbered, so `position` stays contiguous at 1 to 13, which is how the loudness retirement left it. Position is display order only; selections reference the row id.

## Consequences

**A User who had picked it keeps four goals and is not asked again.** `focus_selection` records *that* they answered, which is the row that keeps the first-run dialog from reopening (ADR 0076). They lose a tile and gain nothing in its place, and nothing tells them why. That is the cost, and it is accepted: the alternative is a notice about a goal the application is withdrawing, on a screen the User did not come to for that.

**Wrap-ups written before today keep their `articulation` tags.** They still count in the recurring block, where `ProgressRecurring` renders the raw key without a link, because the goal's page can only say there is nothing under that name. Over six months the retention sweep (ADR 0067) empties the tag out by itself.

**The progress view's text-only group drops from three goals to two**, both of which are answered by what the transcript holds. The count in `focusMetrics.test.ts` is pinned, so a goal moving between buckets fails the suite rather than quietly changing what a screen claims.

**F-38 is untouched and stays open in the feature list.** It is a MUST, and this application does not meet it. Recording the reasons is what ADR 0084 and this one do; a feature list that silently dropped it would be the dishonest version of the same decision.

**The way back is cheap.** Re-adding the entry reactivates the row on the next boot, with the stored selections still pointing at it. Should the recogniser ever be able to transcribe verbatim, or should a measure arrive that separates a speaker from their microphone, nothing here has to be undone first.
