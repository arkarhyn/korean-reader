import type { ReaderDB } from "./db";

// Mirrors PlacementOut in server/app/api/schemas.py.
export type PlacementData = {
  grammar: { id: string; ko: string; en: string }[];
  vocab: { id: string; word: string }[];
  calibration: string[];
  completed_attempt: string | null;
  fitted: boolean;
};

export type Step = "grammar" | "vocab" | "calibration" | "done";

// Saved after every answer so placement resumes where it stopped (phone gets interrupted).
export type PlacementProgress = {
  attempt_id: string;
  step: Step;
  index: number;
  started_at: string;
  rating?: boolean; // calibration: passage read, waiting for the 1-5 rating
  tapped?: number[];
  read_ms?: number;
  done_logged?: boolean;
};

const DATA_KEY = "placement";
const PROGRESS_KEY = "placementProgress";

export function sectionLength(data: PlacementData, step: Step): number {
  return step === "grammar" ? data.grammar.length : step === "vocab" ? data.vocab.length : step === "calibration" ? data.calibration.length : 0;
}

const ORDER: Step[] = ["grammar", "vocab", "calibration", "done"];

export function start(attempt_id: string, now: string): PlacementProgress {
  return { attempt_id, step: "grammar", index: 0, started_at: now };
}

/** Next position after answering the current item; empty sections are skipped. */
export function advance(p: PlacementProgress, data: PlacementData): PlacementProgress {
  const base = { attempt_id: p.attempt_id, started_at: p.started_at };
  if (p.index + 1 < sectionLength(data, p.step)) return { ...base, step: p.step, index: p.index + 1 };
  let i = ORDER.indexOf(p.step) + 1;
  while (ORDER[i] !== "done" && sectionLength(data, ORDER[i]) === 0) i++;
  return { ...base, step: ORDER[i], index: 0 };
}

/** One step back within the attempt (re-answering an item: the server keeps the last answer). */
export function back(p: PlacementProgress, data: PlacementData): PlacementProgress {
  const base = { attempt_id: p.attempt_id, started_at: p.started_at };
  if (p.rating) return { ...base, step: p.step, index: p.index };
  if (p.index > 0) return { ...base, step: p.step, index: p.index - 1 };
  let i = ORDER.indexOf(p.step) - 1;
  while (i >= 0 && sectionLength(data, ORDER[i]) === 0) i--;
  if (i < 0) return p;
  return { ...base, step: ORDER[i], index: sectionLength(data, ORDER[i]) - 1 };
}

/** Share of all items answered, 0..1. */
export function fraction(p: PlacementProgress, data: PlacementData): number {
  const total = data.grammar.length + data.vocab.length + data.calibration.length;
  if (p.step === "done" || total === 0) return 1;
  let doneCount = p.index;
  for (const s of ORDER.slice(0, ORDER.indexOf(p.step))) doneCount += sectionLength(data, s);
  return doneCount / total;
}

async function getJson<T>(db: ReaderDB, key: string): Promise<T | undefined> {
  const v = (await db.meta.get(key))?.value;
  return v ? (JSON.parse(v) as T) : undefined;
}

export const loadData = (db: ReaderDB) => getJson<PlacementData>(db, DATA_KEY);
export const saveData = (db: ReaderDB, d: PlacementData) => db.meta.put({ key: DATA_KEY, value: JSON.stringify(d) });
export const loadProgress = (db: ReaderDB) => getJson<PlacementProgress>(db, PROGRESS_KEY);
export const saveProgress = (db: ReaderDB, p: PlacementProgress) =>
  db.meta.put({ key: PROGRESS_KEY, value: JSON.stringify(p) });
export const clearProgress = (db: ReaderDB) => db.meta.delete(PROGRESS_KEY);
export { DATA_KEY as PLACEMENT_DATA_KEY, PROGRESS_KEY as PLACEMENT_PROGRESS_KEY };
