import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReaderDB } from "./db";
import { setWordState, untap } from "./wordActions";

let db: ReaderDB;
const log = vi.fn(async () => undefined);

beforeEach(() => {
  db = new ReaderDB(`test-${crypto.randomUUID()}`);
  log.mockClear();
});

describe("setWordState", () => {
  it("marks known, logs the previous state, and undoes back to it", async () => {
    await db.lexemeStates.put({ lexeme_id: 7, state: "seen", updated_at: "2026-10-01T00:00:00Z" });
    const prev = await setWordState(db, log, 7, "known", "S01E001");
    expect(prev).toBe("seen");
    expect(log).toHaveBeenCalledWith("set_state", {
      lexeme_id: 7,
      state: "known",
      prev_state: "seen",
      episode_id: "S01E001",
    });
    expect((await db.lexemeStates.get(7))?.state).toBe("known");

    await setWordState(db, log, 7, prev, "S01E001");
    expect((await db.lexemeStates.get(7))?.state).toBe("seen");
  });

  it("'I forgot this' moves a known word to learning", async () => {
    await db.lexemeStates.put({ lexeme_id: 3, state: "known", updated_at: "2026-10-01T00:00:00Z" });
    expect(await setWordState(db, log, 3, "learning", "S01E002")).toBe("known");
    expect((await db.lexemeStates.get(3))?.state).toBe("learning");
  });

  it("treats a word with no state as new", async () => {
    expect(await setWordState(db, log, 9, "known", "S01E001")).toBe("new");
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
