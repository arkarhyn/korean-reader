import type { ReaderDB } from "./db";
import type { EventType } from "./types";

type Log = (type: EventType, payload: Record<string, unknown>) => Promise<unknown>;

// Popover actions (DECISIONS 54). The local state changes at once so coverage and the
// popover reflect it offline; the server applies the same set_state when it syncs.

/** "알아요": mark known. Returns the previous state so the visit can undo it. */
export async function markKnown(db: ReaderDB, log: Log, lexemeId: number, episodeId: string): Promise<string> {
  const prev = (await db.lexemeStates.get(lexemeId))?.state ?? "new";
  await log("set_state", { lexeme_id: lexemeId, state: "known", prev_state: prev, episode_id: episodeId });
  await db.lexemeStates.put({ lexeme_id: lexemeId, state: "known", updated_at: new Date().toISOString() });
  return prev;
}

/** Undo "알아요" within the same visit. */
export async function undoKnown(db: ReaderDB, log: Log, lexemeId: number, prev: string, episodeId: string) {
  await log("set_state", { lexeme_id: lexemeId, state: prev, episode_id: episodeId });
  await db.lexemeStates.put({ lexeme_id: lexemeId, state: prev, updated_at: new Date().toISOString() });
}

export type TapRef = { para: number; start: number; end: number; lex: number };

/** Mistap: the lookup didn't happen. The word_tap stays in the log; word_untap cancels it. */
export async function untap(log: Log, tapped: Set<number>, episodeId: string, t: TapRef) {
  tapped.delete(t.lex);
  await log("word_untap", {
    episode_id: episodeId,
    paragraph_idx: t.para,
    start: t.start,
    end: t.end,
    lexeme_id: t.lex,
  });
}
