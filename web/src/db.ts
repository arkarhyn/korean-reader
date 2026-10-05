import Dexie, { type EntityTable } from "dexie";
import type { Episode, LexemeState, QueuedEvent, ReviewItem } from "./types";

export type Progress = { episode_id: string; completed_at: string };
export type Meta = { key: string; value: string };

// Offline store (DECISIONS 16). `queue` holds events not yet acknowledged by the server.
export class ReaderDB extends Dexie {
  episodes!: EntityTable<Episode, "id">;
  lexemeStates!: EntityTable<LexemeState, "lexeme_id">;
  queue!: EntityTable<QueuedEvent, "id">;
  progress!: EntityTable<Progress, "episode_id">;
  meta!: EntityTable<Meta, "key">;
  reviewItems!: EntityTable<ReviewItem, "lexeme_id">;

  constructor(name = "korean-reader") {
    super(name);
    this.version(1).stores({
      episodes: "id",
      lexemeStates: "lexeme_id",
      queue: "id, ts",
      progress: "episode_id",
      meta: "key",
    });
    // Stage 6: Quick review items from the last sync (replaced on every pull).
    this.version(2).stores({ reviewItems: "lexeme_id" });
  }
}

export const db = new ReaderDB();

export async function getMeta(key: string): Promise<string | undefined> {
  return (await db.meta.get(key))?.value;
}

export async function setMeta(key: string, value: string): Promise<void> {
  await db.meta.put({ key, value });
}
