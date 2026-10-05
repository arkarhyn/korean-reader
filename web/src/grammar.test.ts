import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { ReaderDB } from "./db";
import { lessonList, markIntroduced, recordAnswer, score, splitBlank } from "./grammar";
import type { GrammarPoint } from "./types";

const lesson = (code: string) => ({
  code,
  title_en: code,
  summary_en: "",
  ja_parallel: null,
  ja_diff_note: null,
  notes: [],
  examples: [],
  drills: [],
});

const point = (code: string, teach_order: number | null, state: GrammarPoint["state"] = "new", withLesson = true): GrammarPoint => ({
  code,
  label_ko: code,
  htsk_lesson: null,
  teach_order,
  state,
  ja_parallel: null,
  ja_diff_note: null,
  lesson: withLesson ? lesson(code) : null,
});

describe("splitBlank", () => {
  it("splits around the first run of underscores", () => {
    expect(splitBlank("한번 먹어 ___ 싶어요.")).toEqual(["한번 먹어 ", " 싶어요."]);
    expect(splitBlank("가__")).toEqual(["가", ""]);
  });
  it("returns null without a blank", () => {
    expect(splitBlank("빈칸 없음_")).toBeNull();
  });
});

describe("drill scoring", () => {
  it("counts only the first tap per drill", () => {
    let a = recordAnswer({}, 0, 1, 1);
    a = recordAnswer(a, 1, 0, 2);
    const same = recordAnswer(a, 1, 2, 2); // retap after a wrong answer: ignored
    expect(same).toBe(a);
    expect(score(a, 3)).toEqual({ correct: 1, total: 3 });
  });
});

describe("lessonList", () => {
  it("keeps points with a lesson, in teach order, unordered last", () => {
    const pts = [point("G.C", null), point("G.B", 2), point("G.X", 0, "new", false), point("G.A", 1)];
    expect(lessonList(pts).map((p) => p.code)).toEqual(["G.A", "G.B", "G.C"]);
  });
});

describe("markIntroduced", () => {
  it("moves new to introduced and leaves other states alone", async () => {
    const db = new ReaderDB(`test-${crypto.randomUUID()}`);
    await db.grammar.bulkPut([point("G.A", 1, "new"), point("G.B", 2, "solid")]);
    await markIntroduced(db, "G.A");
    await markIntroduced(db, "G.B");
    await markIntroduced(db, "G.MISSING");
    expect((await db.grammar.get("G.A"))?.state).toBe("introduced");
    expect((await db.grammar.get("G.B"))?.state).toBe("solid");
    db.close();
  });
});
