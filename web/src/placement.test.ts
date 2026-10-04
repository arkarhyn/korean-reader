import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { ReaderDB } from "./db";
import { advance, back, fraction, loadProgress, saveProgress, start, type PlacementData } from "./placement";
import { libraryEpisodes } from "./views/Library";
import type { Episode } from "./types";

const data: PlacementData = {
  grammar: [{ id: "g1", ko: "", en: "" }, { id: "g2", ko: "", en: "" }],
  vocab: [{ id: "v1", word: "" }],
  calibration: ["c1", "c2"],
  completed_attempt: null,
  fitted: false,
};

describe("placement progress", () => {
  it("walks grammar -> vocab -> calibration -> done", () => {
    let p = start("a", "t");
    const seen: string[] = [];
    while (p.step !== "done") {
      seen.push(`${p.step}:${p.index}`);
      p = advance(p, data);
    }
    expect(seen).toEqual(["grammar:0", "grammar:1", "vocab:0", "calibration:0", "calibration:1"]);
    expect(p.attempt_id).toBe("a");
    expect(fraction(p, data)).toBe(1);
  });

  it("skips empty sections and reports progress", () => {
    const noVocab = { ...data, vocab: [] };
    const p = advance({ ...start("a", "t"), index: 1 }, noVocab);
    expect(p.step).toBe("calibration");
    expect(fraction(p, noVocab)).toBe(0.5);
  });

  it("undo goes back across sections and out of the rating screen", () => {
    expect(back({ ...start("a", "t"), step: "vocab", index: 0 }, data)).toMatchObject({ step: "grammar", index: 1 });
    expect(back({ ...start("a", "t"), step: "calibration", index: 1, rating: true, tapped: [3] }, data)).toEqual({
      attempt_id: "a",
      started_at: "t",
      step: "calibration",
      index: 1,
    });
    const first = start("a", "t");
    expect(back(first, data)).toBe(first);
  });

  it("resumes from IndexedDB", async () => {
    const db = new ReaderDB(`test-${crypto.randomUUID()}`);
    await saveProgress(db, { ...start("a", "t"), step: "vocab", index: 0 });
    expect(await loadProgress(db)).toMatchObject({ attempt_id: "a", step: "vocab" });
    db.close();
  });
});

it("library hides placement passages", () => {
  const eps = [{ id: "x", series: "main" }, { id: "placement-cal-1", series: "placement" }] as Episode[];
  expect(libraryEpisodes(eps).map((e) => e.id)).toEqual(["x"]);
});
