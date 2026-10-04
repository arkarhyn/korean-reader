import type { ReaderDB } from "./db";
import { KNOWN_STATES } from "./wordActions";

// Word-set checklists (DECISIONS 67). Mirrors server/app/word_sets.py.

export type SetItem = { ko: string; en: string; lexeme_ids: number[]; known: boolean; rank?: number };
export type WordSet = { id: string; title_ko: string; title_en: string; items: SetItem[] };
export type CommonPage = { offset: number; total: number; items: SetItem[] };

export const COMMON_ID = "common";
const CACHE_KEY = "wordSets";

type States = Map<number, string>;

/** Known if the server says so, or every lexeme is known in the local store (changed since last sync). */
export function isKnown(item: SetItem, states: States): boolean {
  if (item.lexeme_ids.length > 0 && item.lexeme_ids.every((id) => KNOWN_STATES.has(states.get(id) ?? ""))) return true;
  // A local change since the last sync overrides a stale server flag.
  if (item.lexeme_ids.some((id) => states.get(id) === "learning")) return false;
  return item.known;
}

/**
 * State changes for Save: newly checked items -> their not-yet-known lexemes become known;
 * unchecked items that were known -> their known lexemes become learning ("I forgot this").
 * Untouched items change nothing (unmarked words are left alone).
 */
export function diff(items: SetItem[], checked: Set<number>, states: States): { known: number[]; learning: number[] } {
  const known = new Set<number>();
  const learning = new Set<number>();
  items.forEach((item, i) => {
    const was = isKnown(item, states);
    const now = checked.has(i);
    if (now && !was) item.lexeme_ids.filter((id) => !KNOWN_STATES.has(states.get(id) ?? "")).forEach((id) => known.add(id));
    if (!now && was) item.lexeme_ids.filter((id) => KNOWN_STATES.has(states.get(id) ?? "")).forEach((id) => learning.add(id));
  });
  return { known: [...known], learning: [...learning].filter((id) => !known.has(id)) };
}

export async function saveSets(db: ReaderDB, sets: WordSet[]): Promise<void> {
  await db.meta.put({ key: CACHE_KEY, value: JSON.stringify(sets) });
}

export async function loadSets(db: ReaderDB): Promise<WordSet[] | undefined> {
  const raw = (await db.meta.get(CACHE_KEY))?.value;
  return raw ? (JSON.parse(raw) as WordSet[]) : undefined;
}
