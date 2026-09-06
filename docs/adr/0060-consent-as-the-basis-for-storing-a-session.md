# ADR 0060: Consent Is What Permits a Session to Be Stored

## Status

Accepted. Reopens the question ADR 0023 asked and ADR 0034 answered differently; constrains ADR 0034's write path.

## Context

ADR 0023 planned consent-gated storage and then stored nothing at all. ADR 0034 superseded it: Sessions are persisted at the end of every call, unconditionally, because the transcript (F-12), the wrap-up (F-09) and the history (F-13/F-48) are impossible without it. That left the application storing what people say aloud — their name, their company, whatever the scenario drew out of them — with nothing recorded about whether they agreed to it.

ADR 0031 already named the consequence: the Sessions are personal data, the pseudonym does not change that, and "a retention period and a deletion path are open work, not discharged by how this column is designed". ADR 0058 made that more pressing rather than less, by giving users a history they can see and would reasonably expect to be able to remove.

## Decision

A finished Session is stored only if the subject has granted consent to the current wording, and withdrawing that consent deletes what was stored under it.

**Consent is recorded as decisions, not as a state that gets overwritten.** `consent` is append-only: granting, withdrawing and granting again are three rows, and the newest one is what holds. A decision is something that happened at a moment, and a record that overwrites itself destroys the evidence it exists to keep. Idempotence is preserved where it matters — repeating a decision already in force writes nothing, so a double-clicked button does not fill the log.

**The wording is versioned.** `CURRENT_VERSION` changes whenever the notice changes in substance, and every earlier decision becomes stale and is asked again. Consent to a text nobody put in front of the person is not consent, and a silent edit must not keep an old "yes" alive.

**The check happens where the Session is written, not where it starts.** A call runs for minutes; an answer taken at the handshake would be that old by the time the row is written, and someone who withdrew while talking would find the call stored anyway. `api/session_ws.py::_record` asks immediately before persisting, which is the last point at which unconsented data can still be prevented from existing.

**It fails closed.** Everywhere else in this application a database failure is logged and stepped over, because losing a wrap-up beats losing a call (ADR 0016/0034). `consent.allows_storage` inverts that: a question that cannot be answered is answered "no". The same reflex here would store data on a guess, which is the single outcome this decision exists to prevent.

**Declining leaves the trainer fully usable.** The call runs, the transcript is shown afterwards; only the storage, and therefore the wrap-up and the history, are absent. This is deliberate and is the reason consent is a defensible basis at all: one that must be given before anything works is not freely given (Art. 7(4)), and would be the weakest possible footing for exactly the data it is meant to cover. The interface says so before the call rather than after it — a notice on the setup screen, while the user can still change their mind.

**Withdrawal deletes.** Consent is the only basis this application has for keeping the data, so once it is withdrawn there is nothing left to justify keeping it (Art. 17(1)(b)). The decision and the deletion share one transaction, so the outcome is either "withdrawn and empty" or unchanged — never a withdrawal on record whose data is still there, which is the state that would be hardest to notice and worst to be in. The interface confirms in a second step and says what will be destroyed.

**One consent, one purpose.** `purpose` is a named vocabulary with one value today (`session_storage`). ADR 0059's research use of de-identified measurements is the obvious second, and would be a new value rather than a second meaning for this one — but it is not being built now, and until it is, a withdrawal takes the measurements with everything else.

**Seeing, taking and removing, as three routes.** `GET /api/me/data` reports counts and the period they span — the extent of what is held, which a list of transcripts does not convey. `GET /api/me/export` returns every row the subject owns as one nested JSON document, served as a download rather than a page so a tab full of transcripts is not left for the next person at the machine. `DELETE /api/sessions/{extern_id}` removes one training. All three scope by the caller's `sub` in the query itself, and the delete answers 404 for an id that is absent *or* not the caller's, exactly as the read route does (ADR 0050).

The overview and the export are two routes over the same data on purpose. The first is cheap enough to load with the profile screen on every visit; the second is large, slow and only ever wanted deliberately, and serving it where the first was needed would put a full transcript dump behind an ordinary page load.

**The deletion itself is one module.** `backend/deletion.py` is small because the schema does the work: the ownership cascades of ADR 0026/0052 remove Turns, Measurements, Findings, Feedback, FeedbackPoints and AnalysisJobs with the Session, by raw SQL as well as through the ORM, and reference data is untouched by construction. It goes through the ORM rather than one bulk `DELETE`, because the cascades are declared as a pair on purpose and quietly relying on only one of them is how the other stops being maintained.

## Consequences

The application no longer stores a recording of what someone said without a record that they agreed to it, and the user has a way to take it back that actually removes the data rather than only stopping the next write. The consent log makes it answerable, per subject, what was agreed to and when — including decisions that were later reversed.

The cost lands on the product. A user who declines gets a trainer without feedback, which is most of its value; the notice says so plainly rather than letting them discover it after a call. And the wrap-up cannot be generated for them at all, because the generator runs in the worker from persisted data (ADR 0018/0019) — generating it in-process and showing it without storing it is possible and was considered, but it is a different change and is not made here.

**What this is not.** No claim of legal compliance is made in the code, the interface or this document; what is described here are the technical measures and their limits. Three limits are known and named:

- **Backups are not reached.** Checked rather than assumed: `compose.yaml` defines no backup service, the repository contains no `pg_dump` anywhere, and Postgres writes to a Docker named volume. The application therefore makes no second copy of its own. What it cannot see is whatever the hoster does: the deployment runs at Hetzner (see ADR 0020's status update), and any snapshot or volume backup taken there is outside every deletion path here. The privacy statement says so rather than claiming a completeness the system cannot deliver.

  That is not reassurance. It means a lost volume loses every stored training, and it means the moment backups *are* introduced they become a copy no deletion path reaches. Whoever adds them owes this ADR a rotation and retention policy in the same change; adding them silently would turn a deletion that is complete today into one that quietly is not.
- **The plaintext transcript in the log is closed, but by default rather than by construction.** `backend/clients/stt.py` used to write every user transcript to the log file at INFO on every Turn — a copy that survived a withdrawn consent and a deleted training, because no route can reach a log file. It now logs the transcript's *length*, which keeps the signal that made the line worth having (an empty transcript, or the short hallucination Whisper produces on near-silence) and says nothing about the person. The full text returns only under `LOG_TRANSCRIPTS`, which is off unless explicitly set, named for exactly what it does, and announced with a warning at boot while it is on. The same switch covers the persona's line in `tts.py`: that is generated content rather than personal data, but a rule with an exception is harder to keep than one without.

  This is a default, not a guarantee. Anyone who turns the switch on is writing personal data outside every deletion path in this system, and the boot warning says so.
- **Re-identification is unchanged.** ADR 0031's analysis still holds: the mapping from `sub` to a person is one query away for anyone who can read both the realm and the database.

**On the processors.** The user's audio and its transcript go to the DiReKT gateway (STT and LLM). KugelAudio receives only the *generated persona text* for synthesis — no user data reaches it. Recorded here so that a change to either arrangement is noticed as a change.

This decision is expected to be revisited if the legal basis is reconsidered. Consent is not obviously the right basis for a training tool people may be expected to use, and Art. 6(1)(e)/(f) may fit a university research deployment better. That determination is not the code's to make; if it changes, the gate stays useful but the withdrawal semantics above would need rethinking.
