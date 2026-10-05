import type { ReaderDB } from "./db";
import type { GrammarPoint } from "./types";

// Stage 8 grammar track: pure helpers for the lesson view and the grammar list.

const BLANK = /_{2,}/;

/** Split a drill prompt around its blank (two or more underscores). null when there is no blank. */
export function splitBlank(prompt: string): [string, string] | null {
  const m = BLANK.exec(prompt);
  return m ? [prompt.slice(0, m.index), prompt.slice(m.index + m[0].length)] : null;
}

/** First-tap answers per drill index (later taps never count). */
export type DrillAnswers = Record<number, { choice: number; correct: boolean }>;

/** Record a tap; returns the same object when the drill was already answered. */
export function recordAnswer(answers: DrillAnswers, idx: number, choice: number, answer: number): DrillAnswers {
  if (idx in answers) return answers;
  return { ...answers, [idx]: { choice, correct: choice === answer } };
}

/** "N / M right": correct first taps over the number of drills in the lesson. */
export function score(answers: DrillAnswers, total: number): { correct: number; total: number } {
  return { correct: Object.values(answers).filter((a) => a.correct).length, total };
}

/** Points with a lesson, in teach order (unordered ones last, by code). */
export function lessonList(points: GrammarPoint[]): GrammarPoint[] {
  const order = (p: GrammarPoint) => p.teach_order ?? Number.POSITIVE_INFINITY;
  return points.filter((p) => p.lesson).sort((a, b) => order(a) - order(b) || a.code.localeCompare(b.code));
}

/** After grammar_lesson_complete: "new" becomes "introduced" locally until the next pull says otherwise. */
export async function markIntroduced(db: ReaderDB, code: string): Promise<void> {
  const p = await db.grammar.get(code);
  if (p?.state === "new") await db.grammar.put({ ...p, state: "introduced" });
}
