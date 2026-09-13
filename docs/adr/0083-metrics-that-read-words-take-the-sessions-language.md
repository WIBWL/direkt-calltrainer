# ADR 0083: Metrics That Read Words Take the Session's Language

## Status

Accepted. `Conversation` carries the Session's `language_id`, and the word lists that three metrics read live in the `LanguagePack` (ADR 0043's per-Persona language). Introduces the open/closed split in the `questions` detail (F-41), the `fillers` metric (F-51) and the `repetitions` metric (F-08). No migration: metric rows are seeded (ADR 0051), and each new metric is one `MetricDef`.

## Context

Until this, every metric was either acoustic (milliseconds, decibels, Hertz) or language-blind text arithmetic — word counts, question marks. Three things the focus catalogue promises need more than that:

- **What kind of question.** `questions` counts question marks. Whether someone asked "Was brauchen Sie?" or "Passt Ihnen Dienstag?" is the difference that matters for needs analysis, and the count does not see it.
- **Fillers.** The catalogue's "Prägnante Sprache" says "Ausgewertet werden Häufungen von Füllwörtern". Its only backing in the progress view was the word count, which grows with the call and says nothing about concision.
- **Repetitions.** The same goal promises "inhaltliche Wiederholungen", and F-08 names redundancy.

The first two need a vocabulary, and a vocabulary is language-specific. Personas are German or English (ADR 0043), and `metrics.py` had no idea which one a call was in. A German word list applied to an English call measures nothing and reports a zero that looks measured — the failure ADR 0051 refuses everywhere else.

## Decision

**`Conversation.language_id` is the Persona's language, passed in at persistence like the Turns themselves, and each metric that reads words takes its list from that language's pack.** Without a pack the metric reports what it can without a vocabulary, and a metric that is nothing but its vocabulary is absent rather than zero. Packs are looked up with `.get`, not `get_pack`: a missing pack costs one detail, where raising would cost every statistic of the call.

### Open and closed questions are a detail of `questions`, not a metric

A question whose first word is a question word (`open_question_re`: "was", "wie", "womit", …, a short run of leading fillers skipped) is open; anything else is closed. Anchored and deliberately shallow — a question word buried further in counts as closed rather than being guessed at.

It stays inside the `questions` Measurement as `open`/`closed` in the detail, shown as a second line under the count ("davon 3 offen, 5 geschlossen"), rather than becoming a tile of its own. How many questions were open is a reading of the same number, not a second number. Both halves are read off the same question marks, one segment per mark, so they always add up to the count, and a tile that shows both cannot contradict itself.

### Fillers are the lexical ones

`filler_re` lists words that are fillers most of the time they are said: quasi, sozusagen, gewissermaßen, irgendwie, eigentlich, halt, im Prinzip, sag ich mal, sagen wir mal, ehrlich gesagt; for English basically, literally, actually, kind of, sort of, you know, I mean, so to speak. Word-bounded, so "halt" does not match "Haltung" or "enthalten". "like" is left out of the English list because it is a verb or a preposition far more often than a filler.

The value is the count, the detail the rate per hundred words and the words themselves, most frequent first; the tile names the two commonest ("meist „eigentlich" (4×)"), which is the part a user can act on. Hesitation sounds ("äh", "ähm") are a different thing and not in the list: Whisper removes them from the transcript. ADR 0084 reads them off the audio.

A word list is crude. "Eigentlich" and "halt" have legitimate uses, and the count cannot tell them apart; that is why it is a count and not a verdict, and why the words are shown rather than only their number.

### Repetitions need no vocabulary

`repetitions` counts passages of four or more words said again, word for word, later in the user's speech. Four and not three, so "ich habe das" twice is how people talk and not a repetition, while a repeated sentence is. Overlapping matches merge, so one repeated sentence counts once; a later occurrence has to start after the earlier one ends, so "ja ja ja ja ja" does not match its own copies. The detail quotes the passages, so a reader can see what was counted.

It is language-independent and runs whether or not a pack exists.

## Consequences

"Prägnante Sprache" is backed in the progress view by fillers, hesitations and repetitions, with the word count last.

Adding a language means these lists come with its pack, the way its closing patterns and phantom phrases already do. A pack without them would fail at import, which is the point: the metric would otherwise silently measure the wrong language.

All three can be recomputed for stored Sessions, since they read the stored transcript. No backfill script exists yet; until one does they start with the calls recorded after they shipped.
