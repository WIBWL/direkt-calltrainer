import type { SessionSummary } from "../protocol";

/**
 * What the wrap-ups keep coming back to, counted across a user's trainings.
 *
 * The dashboard's block D (docs/dashboard-konzept.md). It invents nothing: the
 * wrap-ups already wrote points of two kinds, and since each point carries the
 * focus goal it is about, they can be counted. What comes out is a **frequency
 * of statements**, never a measurement of a person, which is the distinction
 * that keeps this inside ADR 0004 and ADR 0065.
 *
 * Two decisions that change the number:
 *
 * **Counted per training, not per point** — two improvements about the closing
 * in one call are one call that mentioned it. Counting points would let a
 * single wordy wrap-up look like a pattern.
 *
 * **The denominator is the trainings that could have mentioned it**, i.e. those
 * whose wrap-up carries any assignment. A training with no wrap-up never had an
 * opinion, and one written before the assignment existed could not record it;
 * leaving either in would quietly shrink every fraction. The interface says
 * which number it divides by.
 */
export interface GoalMentions {
  goal: string;
  /** In how many trainings this goal was named, of `total`. */
  count: number;
}

export interface MentionSummary {
  strengths: GoalMentions[];
  improvements: GoalMentions[];
  /** Trainings whose wrap-up carried at least one assignment. The denominator,
   *  and also what says whether this block has anything to stand on. */
  total: number;
}

/** Below this a mention is an observation, not a pattern. One point from one
 *  training says nothing about what recurs, and presenting it as if it did is
 *  the failure this block has to avoid. */
export const MIN_MENTIONS = 2;

/** At most this many per column. The block answers "what keeps coming up",
 *  and a list of eight answers a different question. */
export const MAX_SHOWN = 3;

export function mentionSummary(sessions: SessionSummary[]): MentionSummary {
  const tagged = sessions.filter((session) => session.feedback_goals.length > 0);
  return {
    strengths: rank(tagged, "strength"),
    improvements: rank(tagged, "improvement"),
    total: tagged.length,
  };
}

/**
 * The goals of one kind, most-mentioned first.
 *
 * Ties are broken by goal key rather than left to the sort's input order, so
 * the same data renders the same way on every read. Two goals mentioned three
 * times each should not swap places because a training was added at the other
 * end of the list.
 */
function rank(sessions: SessionSummary[], kind: "strength" | "improvement"): GoalMentions[] {
  const counts = new Map<string, number>();
  for (const session of sessions) {
    // Per training: the same goal named twice in one wrap-up counts once.
    const named = new Set(
      session.feedback_goals.filter((tag) => tag.kind === kind).map((tag) => tag.goal),
    );
    for (const goal of named) {
      counts.set(goal, (counts.get(goal) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .map(([goal, count]) => ({ goal, count }))
    .filter((entry) => entry.count >= MIN_MENTIONS)
    .sort((a, b) => b.count - a.count || a.goal.localeCompare(b.goal))
    .slice(0, MAX_SHOWN);
}

/**
 * One thing a wrap-up wrote about a goal, with the training it was written in.
 *
 * The dashboard counts mentions; this is what was counted. A frequency with no
 * way to read behind it asks the user to take a number on trust, and for the
 * goals with no measurement the sentences are the whole of what exists
 * (ADR 0064's amendment put them on the listing for this).
 *
 * It stays a quotation and never becomes an input: nothing here summarises,
 * groups or weighs the sentences, because that would be a second opinion about
 * a call written without reading it (ADR 0004).
 */
export interface GoalStatement {
  sessionId: string;
  /** ISO 8601, the Session's start. */
  at: string;
  scenario: string;
  persona: string;
  kind: "strength" | "improvement";
  goal: string;
  text: string;
}

/**
 * Everything the wrap-ups wrote about these goals, newest training first.
 *
 * Several goals at once because a metric can stand behind more than one, and
 * the order within a training is the wrap-up's own (`position`), which the
 * listing preserves.
 */
export function statementsFor(
  sessions: SessionSummary[],
  goals: string[],
): GoalStatement[] {
  const wanted = new Set(goals);
  return sessions.flatMap((session) =>
    session.feedback_goals
      .filter((tag) => wanted.has(tag.goal))
      .map((tag) => ({
        sessionId: session.session_id,
        at: session.started_at,
        scenario: session.scenario,
        persona: session.persona,
        kind: tag.kind,
        goal: tag.goal,
        text: tag.text,
      })),
  );
}

/**
 * How often one goal was named, over all trainings that could have named it.
 *
 * For the focus tiles (block B), where the goals with no measurement of their
 * own have something to show. No threshold here, unlike the
 * block above: on a tile the user picked themselves, "once so far" is a
 * legitimate answer to "how is this going", where in a list of recurring
 * themes it would be noise.
 */
export function mentionsFor(
  sessions: SessionSummary[],
  goal: string,
): { strengths: number; improvements: number; total: number } {
  const tagged = sessions.filter((session) => session.feedback_goals.length > 0);
  let strengths = 0;
  let improvements = 0;
  for (const session of tagged) {
    const kinds = new Set(
      session.feedback_goals.filter((tag) => tag.goal === goal).map((tag) => tag.kind),
    );
    if (kinds.has("strength")) strengths += 1;
    if (kinds.has("improvement")) improvements += 1;
  }
  return { strengths, improvements, total: tagged.length };
}
