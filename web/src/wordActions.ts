import type { ReaderDB } from "./db";
import type { EventType } from "./types";

type Log = (type: EventType, payload: Record<string, unknown>) => Promise<unknown>;

// Popover actions (DECISIONS 54, 65). The local state changes at once so the tint and the
// popover reflect it offline; the server applies the same set_state when it syncs.

export const KNOWN_STATES = new Set(["known", "ignored"]);

/**
 * Set a word's state ("known" = I know this word, "learning" = I forgot this, or a
 * previous state to undo). Returns the state it had before, for an undo.
 */
export async function setWordState(
  db: ReaderDB,
  log: Log,
  lexemeId: number,
  state: string,
  context: { episode_id?: string; word_set?: string },
): Promise<string> {
  const prev = (await db.lexemeStates.get(lexemeId))?.state ?? "new";
  await log("set_state", { lexeme_id: lexemeId, state, prev_state: prev, ...context });
  await db.lexemeStates.put({ lexeme_id: lexemeId, state, updated_at: new Date().toISOString() });
  return prev;
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
