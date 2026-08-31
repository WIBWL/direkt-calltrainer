# ADR 0046: Liveliness Is Pursued at the Prompt Layer Before the Turn-Taking Layer

## Status

Proposed

## Context

ADR 0045 makes a call *trainable*: a fixed case, a named success condition, a
Persona with its own objections. It deliberately narrows what the model may
invent. Two of its effects do touch how alive a call feels — a caller that no
longer contradicts its own figures, and two Personas that are distinguishable
by how they push back rather than only by tone — but that is a by-product, not
its purpose.

The separate question it leaves open is that the counterpart still sounds like
a system answering rather than a person on the phone. Three symptoms are
nameable today: the delivery is flat across a whole call regardless of what is
being said; there is no emotional arc, so a caller who was annoyed in Turn 2 is
exactly as annoyed in Turn 8 no matter what the user did; and the Persona never
interrupts, never uses a backchannel, and never starts speaking before the user
has finished.

Three architecturally distinct layers could carry this, and they are not
equivalent in cost.

The **prompt layer** — the frame in `backend/session/orchestrator.py` — is where
every attempt so far has been made, and it is bounded by the small
university-hosted model of ADR 0011.

The **prosody layer** is the TTS call itself. KugelAudio exposes voice
parameters, but ADR 0044 synthesises one stream per sentence-sized chunk, and
the chunker of ADR 0033 splits on punctuation with no notion of what a sentence
means. Varying delivery per utterance therefore needs a decision about *who*
decides the parameters, which today is nobody.

The **turn-taking layer** — a Persona that interrupts or backchannels — is the
expensive one, because it reopens settled decisions rather than extending them.
ADR 0035's barge-in and ADR 0036's VAD filtering are both built around the user
interrupting the Persona. Making that symmetric is a rework of the turn model,
not an addition to it.

## Decision

We will pursue liveliness at the prompt layer first, and treat the turn-taking
layer as out of scope until the prompt layer is demonstrably exhausted. The
prosody layer stays open but unscheduled: it is worth revisiting once ADR 0045
is in and it is clear how much of the flatness was the missing case rather than
the missing delivery.

This is proposed, not agreed. It is recorded now so the question does not get
lost behind ADR 0045's implementation, and so that "make the calls livelier"
stops being a wish and becomes a choice between three named layers.

## Consequences

Work on liveliness stays cheap and reversible for as long as this holds: prompt
wording is one file, and every attempt is a text change rather than a protocol
change.

It also stays capped. If the flatness turns out to be the model's ceiling
rather than the frame's, the prompt layer cannot fix it, and this decision will
have to be revisited rather than pushed harder.

Deferring the turn-taking layer keeps ADR 0035 and ADR 0036 untouched, which is
the point — but it also means the most conspicuous difference between this and
a real phone call, that the counterpart waits politely for its turn every single
time, is knowingly left in place.

Neither this nor ADR 0045 has a way to *measure* liveliness. Both rest on
listening to real calls, so any claim that a change helped is a judgement, not a
number.
