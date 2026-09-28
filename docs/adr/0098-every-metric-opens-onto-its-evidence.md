# ADR 0098: Every Kennzahl Opens Onto Its Evidence, and the Evidence Is Never Recomputed

## Status

Accepted. Builds on ADR 0091, which gave a metric's explanation a module, and stays inside ADR 0004, ADR 0051 and ADR 0078, which refuse it a target. Pinned by `tests/test_metric_readings.py::test_every_active_metric_is_explained`.

## Context

The post-call screen shows sixteen Kennzahlen as tiles. Three of them were links: Sprachmelodie, Unterbrechungen, Sprechlänge am Stück.

Nobody decided that. `MetricSection` turns a tile into a link when the metric has a `Finding` or an entry in `metric_notes`, and `readings.py` held three entries — so the question "does this tile lead anywhere" was being answered by the question "has anybody written an explanation for it yet". The other thirteen tiles stated a figure and stopped there.

A figure with nothing behind it is a particular problem in *this* application, and it follows from a decision that is right. ADR 0004 and ADR 0051 refuse to attach a target to any of these numbers, because none is validated for this population. That refusal leaves a reader holding "4 Wiederholungen" with no direction — and a reader with no direction supplies one, usually "fewer is better". Showing them *which four* is the only answer available that does not invent a norm.

The evidence was there the whole time. Almost every measurement stores a `detail` (ADR 0029): the filler words with their counts, the repeated passages, every pause with its offset and length, the loudness curve, the parts an opening was checked for. The transcript travels on the same route. All of it was being compressed into one grey subline under the number.

The Lautstärke tile made the shape of the problem visible. It returned early from the tile component in order to draw its curve, and an early return cannot be wrapped in a link — so the one tile carrying a drawing was the one tile with no way to see that drawing larger.

## Decision

**1. Every active metric carries an explanation, and that is what makes its tile open.**

`readings.py` now holds an entry for all sixteen. The thirteen new texts live in `backend/feedback/explanations.py` rather than beside their derivations: `metrics.py` is near pylint's module ceiling, and the two texts that explain a *scale* stay beside their thresholds, which is ADR 0078's fifth condition. Each says, in this order, what is counted, how it was arrived at, what it is worth, and where it stops being trustworthy.

The order of cause matters here and is easy to get backwards. A tile is a link **because there is something behind it**, not linked first and filled later. That is why the condition stays "the metric is explained" rather than becoming "the metric exists".

**2. The page behind a tile shows what the figure was read off, and never recomputes it.**

`frontend/src/components/MetricEvidence.tsx` reads the `detail` the measurement was stored with, or quotes the stored transcript. Where the detail holds nothing, the block says so instead of deriving a substitute.

A second arithmetic in the client would eventually disagree with the first, and the screen would then state two different figures for one call — the same failure, one level down, that ADR 0091 removed from the route. Where a quotation has to line up with a count, the client reproduces the backend's own rule rather than a reasonable approximation of it: questions are cut at the question marks, because `metrics._questions` counts exactly those characters; a filler is matched as a whole phrase, lower-cased and with runs of whitespace closed, because that is the form `metrics._fillers` counts in. `frontend/src/utils/transcriptEvidence.ts` states both at the top and is the second place to look when either rule changes.

**3. The evidence explains; it does not judge.**

No target, no colour on a value, no "zu viele". The two traffic lights of ADR 0078 remain the only places in this application where a colour says something about a number, under their seven conditions. A block that shows four counted sentences lets the reader decide what they are worth, which is the entire point of showing them.

### What this cost at the source

Two metrics stored nothing worth showing.

`pace` now stores the words and the phonation time it divides, so its page can show the division. It deliberately does **not** store a tempo per Turn. That would be a statistic about a single utterance, which is what ADR 0051 rules out and what ADR 0081 excepted only for raw facts that are never shown. A course of "how fast were you in each turn" is a different feature and needs its own decision.

`hesitations` now keeps each held sound with the index of the utterance it sat in, so the page can quote that sentence. It cannot point at the word: what was measured is a stretch of flat voicing, and the speech recogniser removes exactly that sound from the transcript, so naming the sentence is as close as the stored facts allow. This is a located event, like the pause offsets and F-51's interruption offsets that are already stored and shown — not a per-Turn statistic.

## Consequences

Every tile with a stored Session behind it opens. A training run without consent (ADR 0066) has no stored Session, so there is no page and the tile stays a plain tile — the one case where a link would lead nowhere is also the one case where nothing was kept.

A metric added to the inventory without an explanation now fails the suite. Before, it would have shipped as a dead tile and nothing would have said so; the same class of silent arrival ADR 0091 was written about.

Every metric names what its page promises (`openHint` in `frontend/src/utils/metrics.ts`). "Ansehen" fourteen times says nothing about which of them is worth the press, so the fallback is left for a key the catalogue has never been taught.

Two footnotes now sit under the grid, because a grid cannot say either thing by being a grid. That a metric which could not be measured leaves **no tile at all** — five of them go together when the silence detection fails over a noise floor (ADR 0085), and until now the screen said nothing and a reader counting nine tiles where they saw fourteen last time had no way to learn why. And that where the wrap-up marked demanding stretches, a second reading of some figures exists one level down (ADR 0081). *Which* metrics are missing is deliberately not named: the frontend would have to guess at the reason, and "Sprechpausen fehlt" invites reading a fault into the speaker rather than into the microphone.

The wrap-up's own points became controls in the same pass, on the same argument. A strength or an improvement carrying a `turn_id` has always printed that moment as a timestamp, and a timestamp is checkable only by somebody who still remembers the call. It now opens the collapsed transcript at that line and marks it (`frontend/src/components/TranscriptFocus.tsx` — a context, because `FeedbackScreen` owns the transcript and takes the report as a finished element; null where a screen has no transcript, and the timestamp is then the plain text it always was).

Some pages remain thin, and visibly so rather than quietly. `reaction_time`, `run_length` and `pace` show the division behind their figure and no list, because nothing located is stored for them. That is the honest state: the audio is gone (ADR 0048), and what was not kept at the time cannot be recovered. It is also the list of candidates for whatever is measured next.

`tone_fit` stays on the Sprachmelodie page and out of the wrap-up, which ADR 0079 decided under its own heading. It was briefly listed as a gap while this work was scoped, and was not one.
