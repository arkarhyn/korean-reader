import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReaderDB } from "./db";
import { markKnown, undoKnown, untap } from "./wordActions";

let db: ReaderDB;
const log = vi.fn(async () => undefined);

beforeEach(() => {
  db = new ReaderDB(`test-${crypto.randomUUID()}`);
  log.mockClear();
});

describe("markKnown / undoKnown", () => {
  it("logs set_state with the previous state and updates the local store", async () => {
    await db.lexemeStates.put({ lexeme_id: 7, state: "seen", updated_at: "2026-10-01T00:00:00Z" });
    const prev = await markKnown(db, log, 7, "S01E001");
    expect(prev).toBe("seen");
    expect(log).toHaveBeenCalledWith("set_state", {
      lexeme_id: 7,
      state: "known",
      prev_state: "seen",
      episode_id: "S01E001",
    });
    expect((await db.lexemeStates.get(7))?.state).toBe("known");

    await undoKnown(db, log, 7, prev, "S01E001");
    expect(log).toHaveBeenLastCalledWith("set_state", { lexeme_id: 7, state: "seen", episode_id: "S01E001" });
    expect((await db.lexemeStates.get(7))?.state).toBe("seen");
  });

  it("treats a word with no state as new", async () => {
    expect(await markKnown(db, log, 9, "S01E001")).toBe("new");
  });
});

describe("untap", () => {
  it("drops the lexeme from the visit's taps and logs word_untap", async () => {
    const tapped = new Set([3, 4]);
    await untap(log, tapped, "S01E001", { para: 1, start: 5, end: 8, lex: 3 });
    expect([...tapped]).toEqual([4]);
    expect(log).toHaveBeenCalledWith("word_untap", {
      episode_id: "S01E001",
      paragraph_idx: 1,
      start: 5,
      end: 8,
      lexeme_id: 3,
    });
  });
});
