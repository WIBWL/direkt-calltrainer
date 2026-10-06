import type { SessionSummary } from "../protocol";

/** What the wrap-ups keep naming (ADR 0004/0065): statements, never a measurement.
 * Per training, not per point; out of the trainings whose wrap-up carries any tag. */
export interface GoalMentions {
  goal: string;
  count: number;
}

export interface MentionSummary {
  strengths: GoalMentions[];
  improvements: GoalMentions[];
  /** The denominator. */
  total: number;
}

/** Below this a mention is an observation, not a pattern. */
export const MIN_MENTIONS = 2;

const MAX_SHOWN = 3;

export function mentionSummary(sessions: SessionSummary[]): MentionSummary {
  const tagged = sessions.filter((session) => session.feedback_goals.length > 0);
  return {
    strengths: rank(tagged, "strength"),
    improvements: rank(tagged, "improvement"),
    total: tagged.length,
  };
}

/** Ties broken by key, so the same data renders the same way. */
function rank(sessions: SessionSummary[], kind: "strength" | "improvement"): GoalMentions[] {
  const counts = new Map<string, number>();
  for (const session of sessions) {
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

/** Always quoted, never summarised or weighed (ADR 0004). */
export interface GoalStatement {
  sessionId: string;
  at: string;
  scenario: string;
  persona: string;
  kind: "strength" | "improvement";
  goal: string;
  text: string;
}

/** Newest training first, then the wrap-up's own order. */
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

/** For the focus tiles: no threshold, since "once so far" is an answer on a picked goal. */
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
