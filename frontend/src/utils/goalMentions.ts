import type { SessionSummary } from "../protocol";

/** What the wrap-ups keep naming, per focus goal (block D, ADR 0004/0065): a
 * frequency of statements, never a measurement. Counted per training, not per
 * point, so one wordy wrap-up is no pattern; the denominator is trainings whose
 * wrap-up carries any goal tag, since the others could not have named it. */
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
const MAX_SHOWN = 3;

export function mentionSummary(sessions: SessionSummary[]): MentionSummary {
  const tagged = sessions.filter((session) => session.feedback_goals.length > 0);
  return {
    strengths: rank(tagged, "strength"),
    improvements: rank(tagged, "improvement"),
    total: tagged.length,
  };
}

/**
 * The goals of one kind, most-mentioned first; ties broken by goal key so the
 * same data renders the same way on every read.
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
 * One thing a wrap-up wrote about a goal, with its training: what the counts
 * count (ADR 0064's amendment). Always quoted, never summarised or weighed,
 * which would be a second opinion on a call nobody read (ADR 0004).
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
 * Everything the wrap-ups wrote about these goals, newest training first;
 * within a training in the wrap-up's own order (`position`).
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
 * How often one goal was named, over all trainings that could have named it,
 * for the focus tiles (block B). No threshold: on a goal the user picked,
 * "once so far" is a real answer.
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
