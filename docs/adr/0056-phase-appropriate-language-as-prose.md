# ADR 0056: Phasengerechte Sprache Is a Paragraph, Not a Metric

## Status

Accepted. Applies ADR 0049 and ADR 0051 to F-42.

## Context

F-42 (COULD, from R-13) asks the system to recognise the phase a conversation is in and to judge whether the register fits it. The metric inventory in `backend/feedback/metrics.py` has carried a `phase_appropriate_language` entry since ADR 0051 — seeded so the vocabulary is complete, inactive, and with no derivation behind it.

The underlying model of a service encounter (Packard, Li & Berger 2024) is a sequence of three phases with a different register in each: an **Opening** that is warm and relationship-oriented, a **Core Business** stretch that is factual and respects the caller's time, and a **Closing** that returns to warmth. The finding that matters for training is not about any one phase but about the *movement* between them. A caller whose agent stays factual from the first word to the last rates the encounter lower on empathy and satisfaction even when every answer was correct.

That is what makes F-42 awkward for the machinery this codebase already has. ADR 0051 puts every statistic on the Session and forbids target ranges; ADR 0049 keeps figures out of the model's hands entirely. A number for "phase fit" would have to be either a similarity score against a reference register — which needs a corpus nobody has collected — or a threshold invented on the spot, which ADR 0004 calls a score in disguise.

The same source names a second effect: the peak-end rule, under which the closing shapes the memory of the whole call disproportionately. Its natural implementation is to weight the closing more heavily in scoring. There is no scoring here to weight.

## Decision

**F-42 ships as prose, not as a Measurement.** The wrap-up gains a fourth field, `feedback.phase_language`, written in the same LLM call as the summary and the two point lists and shown as its own block below the figures in `FeedbackView`. The inactive `phase_appropriate_language` metric stays inactive and keeps its seeded row; nothing will ever derive a value for it.

The reason is the shape of the observation, not squeamishness about numbers. What the feature reports is a change of register over time. A single figure cannot carry a trajectory, and three figures — one per phase — would need the three norms ADR 0051 declined to invent, one for each.

**One model call, not two.** The phase analysis is read off the same transcript as everything else in the wrap-up. A dedicated second call would isolate the prompt but buy nothing except latency and a second way to fail; the prompt already carries the rules the block needs (quote the trainee, no scores, no invented figures) and the new section refers back to them rather than restating them.

**The peak-end rule is applied as text weight.** The prompt requires the closing to occupy more of the paragraph than the other two phases, and to have first claim on the one concrete suggestion the block ends with. That is the only currency available under ADR 0004.

**The field is nullable, and empty means absent.** The key is defaulted on the response model, so a model answer that drops it still yields a valid wrap-up; a missing or blank paragraph is stored as NULL and the frontend omits the block entirely rather than showing an empty card. A Session analysed before this existed therefore reads as "not analysed", which is true.

## Consequences

F-42 leaves COULD status without a single threshold being invented, and the block reads as an observation rather than as a seventh number the user has to interpret.

It is also the one part of the wrap-up with no deterministic backing. Every figure elsewhere can be traced to Praat or to the transcript (ADR 0049); which phase an utterance belongs to is the model's own judgment, made from the transcript alone with no segmentation upstream. A misplaced boundary produces confident prose about a phase that was not there. The prompt mitigates this — the model works the boundaries out explicitly and is told to say when a phase never happened — but nothing verifies it, and the block cannot be checked the way a citation is checked against the Session's Turn ids.

The wrap-up prompt grows by roughly a fifth. Against a small model (ADR 0011), added length competes with the rules already in it, and the risk is borne by the whole wrap-up rather than by the new block alone. `tests/test_wrapup_prompt.py` guards the text handed to the model; that the model then obeys it is only observable in real calls, as with every other prompt in this codebase.

Making the phase analysis quantitative later means a new metric with a derivation and a validated norm behind it, not a change to this block. The prose stays either way: the register question is one a figure was never going to answer.
