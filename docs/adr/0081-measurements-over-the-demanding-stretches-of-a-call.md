# ADR 0081: Measurements Over the Demanding Stretches of a Call

## Status

Accepted. Amends ADR 0051 on two points, both named below; everything else in that decision stands, the refusal of target ranges above all. Introduces migration `f3a5c81be47d`. Closes the gap `docs/dashboard-konzept.md` section 4.2 records against F-62's "Souveränität unter Druck".

## Context

Fourteen focus goals (ADR 0076, as amended). One of them asks a question no figure in this application could answer: does the way somebody speaks hold up when the other side pushes back. The catalogue text says so outright — "Ausgewertet wird, wie sich Ihre Werte in diesen Passagen vom Rest des Gesprächs unterscheiden" — and nothing was measured that way, because ADR 0051 made every statistic a statement about the whole call, and a whole call contains both stretches averaged into each other.

The dashboard made the gap visible. Every goal with a measurement got a chart; this one got a count of how often the wrap-ups had mentioned it. That is honest, and it is what the six text-only goals still get, but this goal is not like them: the figures it wants *exist*, they are simply computed over the wrong span.

Three obstacles sat in the way, and the shape of this decision is the shape of them.

**The split is a judgement about content.** Whether an exchange was demanding cannot be read off the audio. An objection and a friendly question have no acoustic signature in common. The language pack carries a `still_pressing_re` used to decide whether a reply ends on a demand — it was tuned for detecting call endings and a neutral question ending in a question mark matches it, so a split built on it would be a regex deciding what "under pressure" means.

**The audio is gone.** ADR 0048 discards the recording when the call ends, and the measurement runs inline at that moment. Anything that needs to know *which* exchanges to measure has to know it by then.

**The judgement arrives late.** The wrap-up runs in the worker, minutes after the audio was discarded, and it is the one place in the system that reads the call for what was said in it.

## Decision

**The same Kennzahlen are measured a second and a third time, over the exchanges where the partner pushed back and over the remainder.** `measurement.segment` says which of the three a row describes: `call`, `pressure`, `rest`.

### The wrap-up marks the stretches

`pressure_turns` is a sixth key in the wrap-up's JSON: the ids of the partner utterances that put the trainee under pressure — an objection, a complaint, a refusal, a demand, a challenge, or asking again for something already asked for and not given. The prompt rules it out for a neutral question, and says outright that an empty list is a normal answer, because a model asked to find something will find something.

In the model call that already happens, not a new one. Everything it needs is the transcript it is already reading, and a second call would be a second latency and a second way for the wrap-up to fail.

Marks are on the partner's lines; the figures are about the trainee. **A user utterance belongs to the stretch of the line it answers** — that is the causal direction and it is what the split means. A test pins it, because an off-by-one here measures the wrong sentences while looking entirely healthy.

An id that is not this Session's, or is not a partner line, is dropped. The rule a point's `turn_id` already follows, for the same reason: a reference leading somewhere else is worse than none.

### The facts of each utterance are kept — the first amendment to ADR 0051

`turn.acoustics_json` stores what `acoustics.py` measured for one user utterance: speaking time, phonation, its pauses, its stretch of the loudness curve. ADR 0051's first bullet says a Measurement hangs off the Session and a Turn keeps only its text and its position. That is narrowed here, and the narrowing is deliberately small:

- What is stored per utterance is **raw facts, never statistics**. No rate, no share, nothing derived, and nothing anybody is shown. ADR 0051's rule is about the frame of reference of a figure a user reads, and that is untouched: every Measurement still describes a stretch of conversation.
- It is stored **because it cannot be recovered**. This is the same lesson ADR 0048 keeps handing out in the form of features that can only start on the day they ship. Keeping the facts means a later change to how a call is divided can be applied to the calls already stored, instead of being lost against six months of recordings that no longer exist.

### The whole-call rows are never rewritten

They are measured when the call ends and they stay. A model's opinion about which exchanges were demanding may add figures beside them; it may not change one. `_store_segments` deletes and rewrites the segment rows only, is idempotent for `scripts/requeue_feedback.py`, and sits behind its own failure boundary — these figures are an addition to a wrap-up, and losing them is a smaller loss than losing the wrap-up they hang off.

### Which metrics, and the second amendment

Five: Redeanteil, Sprechtempo, Sprechpausen, Sprechlänge am Stück, Lautstärke. The ones that stay defined on a part of a call.

Left out on purpose: Reaktionszeit is measured from the end of the *previous* partner line, which at a segment boundary lies in the other segment, so the figure would quietly describe the boundary. Fragen and Wortanzahl are counts, and a count over a shorter stretch is a smaller number by construction. The Sprachmelodie needs more voiced speech under it than a stretch usually holds (F-35, ADR 0077).

Loudness is in it, and this is the second amendment. The figure is a *range within one recording*, and within one call the microphone and the distance to it are constant, so comparing one stretch against another is valid even though the absolute level says nothing — the very reason the focus goal about loudness was retired (ADR 0076's amendment). What is compared here is never a level.

A segment under three user utterances is not measured at all. Two utterances are two sentences, not a stretch of a conversation.

### Nothing compares the two figures

No difference, no ratio, no index, no colour, and no word like "stable". The two numbers are put side by side and the reader draws the comparison.

This is ADR 0051's refusal applied exactly: how large a gap means something is a norm nobody has measured for this population, and a "composure" number would be that invented norm wearing a name. ADR 0078's traffic light does not apply either — its first condition is a classification with a published scale behind it, and there is none here.

What the interface does carry is the caveat, twice: which exchanges were demanding was decided by a language model, the figures sitting on that split were measured, and the two are not the same kind of thing.

## Consequences

F-62's "Souveränität unter Druck" has a measurement, and it is the first figure in this application that describes a *part* of a call. The dashboard's stage 3 loses its largest open item; what remains there is the articulation, which needs a measurement that can separate a speaker from their microphone and therefore probably does not arrive.

**Stored Sessions gain nothing.** Their utterances carry no facts and never will — ADR 0048 again. They keep their whole-call figures, and the interface says the comparison does not exist for them rather than showing an empty block. Re-queueing a wrap-up over an old Session produces its `pressure_turns` and no segment rows, which is the honest outcome and not a bug.

The split is only as good as the model that makes it. A wrap-up that marks everything, or nothing, produces a comparison between two stretches that are not what they claim to be, and nothing downstream can detect that. The mitigations are the prompt's (an empty list is normal, a neutral question is not pressure) and the interface's (the caveat), and neither is a guarantee. Pilot data is what would show whether the marking is stable; until then this figure is weaker than the ones beside it, and it is labelled that way.

`turn` now carries a JSON column that nothing queries. It is read by exactly one module, in Python, and folded straight back into the in-memory `Turn` the derivations already take. If a second reader ever appears, that is the moment to ask whether it should have been columns.

The wrap-up prompt has a sixth key. It is the only one nobody reads, which makes it the one whose loss is silent: a model that drops it costs a Session its comparison, and the job still reports success. That is the right trade — the wrap-up is what the user came for — but it means the feature degrades quietly rather than loudly.
