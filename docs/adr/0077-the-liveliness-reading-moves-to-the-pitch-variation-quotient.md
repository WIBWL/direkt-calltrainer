# ADR 0077: The Liveliness Reading Moves to the Pitch Variation Quotient

## Status

Accepted. Amends ADR 0051's exception for F-35 and replaces the five-step scale
introduced with it. No migration: the reading was never stored.

## Context

F-35 reports the shape of a speaker's pitch across a call. Four figures describe
it, and one of them — the range, the 5th-to-95th-percentile span in semitones —
carried a five-step reading: *stark monoton / monoton / ausgewogen / lebendig /
überzeichnet*, at 4, 7, 12 and 18 semitones.

That reading was the deliberate exception to ADR 0004/0051, which rule out
judging a metric against a threshold on the grounds that none is validated for
this population. It was asked for explicitly, and the boundaries were defended
as follows: the F0 standard deviations usually reported for speech are around
1 semitone for monotone delivery, 2 to 3 for conversation and 4 and above for
animated speech; a roughly normal distribution puts a 5th-to-95th span at about
3.29 standard deviations; multiply through and the boundaries fall out.

A literature review was run against that derivation. It found nothing behind
either half of it. No source in the reviewed set states those span figures, none
states the distribution of log F0 that the conversion assumes, and none reports
either for German. The derivation was two unsupported steps stacked on each
other and presented with the confidence of a citation — which is worse than an
openly invented threshold, because it cannot be argued with.

The same review turned up three things that *are* supported, and this ADR is
what follows from them.

## Decision

### The reading moves off the range and onto the pitch variation quotient

Hincks (2005) measured the pitch variation quotient — the standard deviation of
F0 over its mean, in Hertz, computed per 10-second window of speech and then
averaged — against the liveliness ratings of human listeners, and reports where
monotone ends and lively begins: below 0.15, 0.15 to 0.25, above 0.25. The mean
of nine such windows correlated at r = 0.83 with those ratings.

So the reading sits on the figure with the evidence. Three steps and not five,
because three is what Hincks reports; inventing a fourth boundary to sit between
them would put back exactly what this change removes.

The range stays the metric's headline number and loses its verdict. It is
still the right thing to report — it is what the contour drawing shows and what
the metric's unit is in — and there is still no published figure saying where a
narrow span ends and a wide one begins.

The quotient is computed in Hertz, against Hincks's definition rather than
converted to semitones like everything else in the module. A quotient of two
frequencies is dimensionless and normalises across voices by construction, which
is the same job the semitone conversion does elsewhere; and following her
definition exactly is what makes her boundaries apply to the figure at all.

Windowing is not incidental to the measure. A quotient over the whole contour
counts the drift from one utterance to the next as though it were movement
inside a phrase, so a speaker who opened high and finished low reads as lively
without having moved within a sentence.

### The top step is not a warning

The old scale's fifth step, *überzeichnet*, said a very wide span was either
exceptional expressiveness or a tracking error. Nothing supports the first
reading as a fault. In Hincks's corpus, above 0.25 is simply where the liveliest
speakers sat. The step is *sehr lebendig*, and the scale has no bad end.

### The classification carries a traffic light

So that a reader gets an impression of the call before the reading starts. The
wrap-up hands them nine figures at equal weight and says nothing about which one
is worth their attention; colour is the only channel on that screen that answers
that at a glance.

The general rules for this live in **ADR 0078**, written immediately after this
one, once it was clear that a second light meant a pattern rather than a second
exception. This ADR is one instance of it and satisfies its seven conditions:
the colour sits on a classification and not on a figure, the whole scale is
shown in percent beside it, the step is always written out in words, the caveat
names the population the boundaries came from, the colour is served from beside
the threshold, the direction each colour claims is written down in
`intonation.LIGHTS`, and none of it appears on the progress view.

A traffic light claims a direction whether or not one is intended, so the three
colours are stated plainly, per ADR 0078's sixth condition.

- **monoton is red.** The end F-35 exists to make visible. Not a moral fault,
  but the one step where something is reliably harder for the listener: on the
  telephone, with no face to read, a flat delivery costs the emphasis that
  carries the meaning.
- **lebendig is green.** Where Hincks's listeners heard ordinary, engaged
  speech.
- **sehr lebendig is yellow, and this is the one that had to be argued.** It is
  *not* a claim that expressiveness is a fault; nothing reviewed supports that.
  The yellow marks the one region where the *figure* is least trustworthy. An
  octave error inflates a standard deviation badly, and the review's own caveat
  is that high variation is also what nervousness and disfluency produce. It
  means "worth a look at the contour", and the interface says exactly that
  instead of leaving the colour to imply something harsher.

**The colour goes on the classification, never on the semitone figure.** The
step is read from the pitch variation quotient and the metric's number is the
range, so colouring the number would put a colour over a measurement it was not
read from. On the wrap-up tile this needs no special case: that tile already
leads with the word for intonation and keeps the semitones in its subline.
The light travels as `liveliness_light` beside `liveliness_label`, from the same
place the threshold lives; nothing in the frontend maps a step to a colour.

### The block on the metric's page is rebuilt around it

The old layout put a paragraph of method under every figure, which meant the one
sentence a reader acts on sat in the middle of six hundred words about
measurement. It is now the contour, one lead sentence carrying the coloured
classification and what it sounds like to the other side, the five figures as
figures with no prose at all, at most two short sentences where a figure means
something on its own, and everything about method and evidence behind an
`InfoDetails`. Nothing was deleted, only moved, and the limits are the *first*
heading inside the info block rather than the last: a reader who opens it after
seeing a colour is asking what that colour is worth.

### The level threshold for terminal contours is derived, not chosen

An utterance's ending counted as level below 2.0 semitones across the final
400 ms, described in the code as "around the smallest interval a listener
reliably hears as a direction". The review found no support for that figure
either, and found the thing that actually answers the question: the glissando
threshold, below which a pitch movement is not heard as a movement at all.
For continuous speech it is G = 0.32/T² semitones per second (Mertens 2004;
0.16 is the isolated-vowel figure and keeps intra-syllabic glides nobody hears).
Across a window of T seconds that comes to 0.32/T semitones — 0.8 over 400 ms.

The threshold is now computed from that constant. The old figure was two and a
half times the perceptual floor and filed endings as level that a listener hears
as directional.

### The second pitch pass gets Hirst's later ceiling

`acoustics.py` measures F0 twice, the second pass windowed on the first pass's
own quartiles. The ceiling factor was 1.5 × q3, from De Looze (2010). Hirst
(2011) reports that on expressive speech that ceiling sits below the speaker's
own rises and produces systematic octave *halving*. This application measures
people arguing a case on the telephone, where expressive rises are the normal
material, so the factor is 2.5 × q3.

The two figures are a real disagreement in the literature and the choice is a
judgement about which material we have. It costs a little protection against
octave doubling at the top; the percentile trim in `intonation.py` stays where
it is for that reason.

### The unit does not change

The review's one clear negative result. The alternative to semitones is the
ERB-rate scale, which Hermes & van Gestel (1991) preferred for judgements of
prominence. Nolan (2003) tested both on span, which is what F-35 measures, by
having listeners imitate intonation spans across male and female voices:
semitones and ERB-rate both beat Hertz, Mel and Bark by a wide margin, and
semitones came out slightly ahead of ERB (relative error 31%/21% against
35%/25%, against 40%/43% for Hertz). Semitones stay, and now with a reason
rather than a convention behind them.

## Consequences

**Old Sessions lose their step rather than being relabelled.** The reading is
derived on read (`api/sessions.py::_served_detail`), which is what let the scale
be replaced without a migration — but it now needs a figure those Sessions do
not carry, and the audio to compute it from is gone (ADR 0048). Reading the step
off the stored range instead would reinstate the withdrawn scale under a new
name. The block says so and shows four figures instead of five.

**The endings counts shift, and it cannot be checked against stored data.** The
terminal slope needs the 10 ms contour and only the thinned curve is kept, so
the new threshold cannot be applied retrospectively to see what it would have
said. It is a better-founded number, not a verified one, and the counts are
worth eyeballing on the first real calls after it ships.

**The second light is what turned an exception into a pattern.** ADR
0004/0051/0065 had been left unchanged for the first one on the argument that it
was a single trial on a single metric, and that argument does not survive
being made twice. Rather than leave the written rule contradicted by the
application twice over, **ADR 0078** settles what an honest use of colour is and
under what conditions. A third light is now a question of whether it meets those
conditions, not a fresh argument from first principles.

**The boundaries are still not validated for this population, and the caveat is
now heavier rather than lighter.** They come from 18 Swedish students presenting
in L2 English on a room microphone. This is German, spontaneous, sometimes
adversarial, over a telephone band that cuts below 300 Hz. No source reviewed
addresses whether any of that transfers. The interface therefore names the
population wherever it shows the step, which the old scale never did — it said
"not validated for this user group" without saying what it *was* validated on.
The exception to ADR 0004/0051 stands, on better ground and with the same
confinement: this screen only, never the progress view (ADR 0065).

**The review named two things worth knowing that this change does not act on.**

Prosogram-style stylisation of the whole contour (Mertens 2004) would replace
every sub-threshold movement with a level tone before anything is counted, and
would retire the two hand-set filters in the movement figure. It is defined over
vowel nuclei — segmented from the intensity peak, −3 dB left and −9 dB right —
and the intensity curve lives in `acoustics.py` on a different grid and is not
carried alongside the pitch. The terminal contour is the one place the segment
is already known, which is where the threshold is applied.

F0 alone does not carry perceived liveliness. In Hincks's own data, fluency —
mean length of runs between pauses — correlated *more* strongly with liveliness
ratings than the quotient did for female speakers (r = 0.72 against 0.64). The
figures for that are already measured (`phonation_share`, the pause timeline);
nothing combines them, and nothing here claims F-35 is the whole answer. The
interface says as much: high variation is also what nervousness and disfluency
produce.
