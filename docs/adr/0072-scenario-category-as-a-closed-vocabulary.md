# ADR 0072: The Scenario Category as a Closed Vocabulary

## Status

Accepted. Replaces an earlier, now withdrawn decision to drop
`scenario.scenario_type` (migration `e4a9c07b2f31`), whose ADR was removed when
the category came back. The number 0062 stays unused; ADR numbers are not
reassigned.

## Context

The library now ships seventeen Scenarios instead of five. The scenario
catalogue's S-01 to S-05 and S-07 to S-13 were written into the seed alongside
the five that were already there. Two of the catalogue's fourteen entries are
deliberately absent: S-06 needs a memory that spans Sessions (F-23, not built),
and S-14 is not a Scenario at all, because since ADR 0043 the language belongs
to the Persona, so "the same call in English" is an English Persona.

At seventeen cards the selection screen no longer reads at a glance, and the
four filters it has (Alle / Standard / Individuell / `<Unternehmen>`, ADR 0060)
do not help: they answer *whose* Scenario this is, and every one of the
seventeen answers that the same way. What a user picking a training case wants
to narrow by is the kind of call. A five-minute support fault is a different
exercise from an hour of requirements work.

### The column existed once and was removed

`scenario.scenario_type` was `String(60)` of free text, NOT NULL, exposed as an
optional "Kategorie (optional)" input in the authoring editor. It was dropped
because nothing read it: not the prompt (`backend/session/orchestrator.py` never
touched it), not the selection card, not a filter.

The deeper problem was that it had no vocabulary, and the seed shows what that
produced. These were the values across all five Scenarios at the time:

| Scenario | `scenario_type` |
|---|---|
| cold-call-followup | `Offer & Pricing Call` |
| price-cancellation-risk | `Offer & Pricing Call` |
| escalation-repeated-outage | `Beschwerde und Eskalation` |
| upsell-seat-expansion | `Terminvereinbarung und Ausbau` |
| closing-after-handover | `Abschlussgespräch nach Übergabe` |

Five rows, four distinct values, two languages mixed. The seed comment claimed
the field "follows F-03's categories of Scenario types", but F-03 has three
categories and none of these five is one of them. `cold-call-followup` was
labelled a pricing call although the case is a support ticket that has been open
eleven days with no price in it anywhere. Nothing caught that, because nothing
read the value.

No filter can be built on this. A filter needs a fixed set of options; grouping
by `distinct(scenario_type)` would have produced four buttons for five cards,
one of them in English. That is not an implementation gap to be tidied up later,
it follows from free text with nothing checking it.

## Decision

`scenario.category` holds one of four values (`operations`, `requirements`,
`pricing`, `closing`) or NULL.

### Where the four come from

They refine F-03's three call contexts. Every category belongs to exactly one
F-03 type, so the catalogue's coverage table (section 6.1) still proves what it
proved, only more precisely:

| key | German label | F-03 | n |
|---|---|---|---|
| `operations` | Betrieb & Störung | short support cases | 6 |
| `requirements` | Beratung & Anforderung | consultative project talks | 5 |
| `pricing` | Preis & Kondition | offer and pricing calls | 3 |
| `closing` | Abschluss & Einwand | offer and pricing calls | 3 |

Two choices are worth stating.

**Why four and not three.** F-03's offer-and-pricing context is the only one
that holds two different exercises. Talking a rate down (`price-cancellation-risk`,
`change-outside-contract-scope`, `procurement-price-negotiation`) and getting to
a commitment against resistance (`upsell-seat-expansion`,
`closing-after-handover`, `technology-choice-objections`) ask different things of
the trainee, and a user picking a training case is choosing between exactly
that. Splitting it also evens the library out, from 6/5/6 to 6/5/3/3. The other
two contexts hold one exercise each and are not split. A finer cut than this was
considered and rejected: at seventeen Scenarios, seven categories would average
2.4 cards per option, and a filter whose options each yield two cards saves
nobody anything.

**Why the labels name the occasion.** "Support" and "Beratung" name a
department. They are accurate and say nothing about what one would practise
there, which is what the filter is for. "Betrieb & Störung" and "Beratung &
Anforderung" name the reason for the call instead. The keys stay short and
English for the wire (ADR 0057/0061); the two-word German labels are display
only.

The assignment of the twelve catalogue Scenarios is not our judgement: the
catalogue files every entry under exactly one F-03 type, and the seed follows it
row for row. The five older Scenarios had no usable value to carry over (see the
table above) and were assigned here, which cost some detail:
`escalation-repeated-outage` was "Beschwerde und Eskalation" and is now Betrieb
& Störung, `upsell-seat-expansion` was "Terminvereinbarung und Ausbau" and is
now Abschluss & Einwand. A free-text label holds more about a single case than a
bucket does. That is the price of being able to filter, and it is paid
knowingly.

### How it is enforced

- **Closed, at the database.** A CHECK constraint (`category_valid`), written
  the same way as `visibility` and the other vocabularies of ADR 0053, is the
  authority. `SCENARIO_CATEGORIES` in `backend/db/models.py` is the list, and
  the API's request pattern is derived from that same tuple, so the two cannot
  drift.
- **English on the wire** (ADR 0057/0061). The German labels live in
  `frontend/src/scenarioLibrary.ts`, in one map that both the filter and the
  editor's select read.
- **Display and filter only.** `backend/session/orchestrator.py` does not read
  it. What the model gets is still `description` plus the three case fields
  (ADR 0045). A category is how a user finds a Scenario, not part of the call.
- **Nullable, and optional in the editor.** A Scenario that fits none of the
  four is better uncategorised than filed under one nobody chose, and a row
  authored before this column existed has nothing to backfill with. Such a row
  is listed under "Alle" and under no category, which is also why every seeded
  Scenario carries one, enforced by a test.

### The filter it feeds

Two rows on the selection screen, both the same component (`FilterSlider`), so
the second cannot end up smaller than the first by drifting apart:

- **Level 1, origin:** Alle / Standard / Individuell / Folgegespräch /
  `<Unternehmen>`
- **Level 2, thematic category:** Alle / Betrieb & Störung / Beratung &
  Anforderung / Preis & Kondition / Abschluss & Einwand

The rows are independent and combine. Each option shows how many Scenarios it
would yield under the *other* row's selection, so an empty option is visible
before it is picked rather than after.

Each row is a `radiogroup` rather than an `<input type="range">`, because the
options are nominal. A range input would imply an order between "Betrieb &
Störung" and "Preis & Kondition" that does not exist, and announces itself to a
screen reader as a number. Arrow keys move the selection, so it behaves like a
slider on the keyboard as well as under the mouse.

Level 1's **Folgegespräch** has nothing behind it yet. A follow-up call
continues an earlier Session, which needs F-23's cross-Session memory, and that
is not built. The option therefore lives in the frontend only, matches nothing,
counts zero and says so in the empty state. No column is added for it: a column
with no writer and no reader is what got `scenario_type` removed, and adding one
speculatively would repeat that. When F-23 lands, the predicate in
`matchesFilter` is one line.

## Consequences

One additive migration (`f5b2d47a91c3`): a nullable column plus its CHECK. No
backfill, so it runs on a populated database without touching a row.

The authoring form gains a field back, now a select over three values instead of
a free-text box. That is a smaller ask of an author than the field it replaces
was, and it is the first time the value they set does something.

A fifth category is one entry in `SCENARIO_CATEGORIES`, one entry in the label
map, and a constraint swap in a migration. The CHECK-over-ENUM choice of ADR
0053 is what keeps that to one line.

With seventeen Scenarios across four categories the selection screen shows six
at most under any single one. That is the point of the change, and also its
ceiling. A library several times this size would want search, not more filters.

The level 2 labels are two words each, so the row is wide: on a narrow viewport
it scrolls horizontally inside its own track rather than wrapping. That is the
cost of labels that say something, and it was preferred to one-word labels that
do not.

`Vertriebsnähe` (neutral / beratungsnah / verhandlungsnah), the second axis the
catalogue proposes, stays out of the data model. The catalogue itself does not
commit to it: K-01 is undecided, arc42's RI-03 proposes distinguishing by
technical depth instead, and the catalogue calls the attribute "ein
Katalogattribut, nicht ein zugesagtes Produktverhalten". If K-01 is ever
decided, it is a second column and a second control, not a re-reading of this
one. The two attributes cut the library differently, and collapsing them would
decide K-01 by accident.
