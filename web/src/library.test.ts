import { describe, expect, it } from "vitest";
import { buildSections, mainPosition, upNext } from "./library";
import type { Episode } from "./types";

const ep = (id: string, series: string): Episode => ({
  id,
  series,
  title_ko: id,
  title_en: id,
  register_tags: [],
  target_grammar: null,
  coverage: 0.95,
  updated_at: "",
  paragraphs: [],
  questions: [],
  lexemes: {},
});

const all = [
  ep("legacy-002", "legacy"),
  ep("S01E010", "main"),
  ep("placement-cal-1", "placement"),
  ep("S01E002", "main"),
  ep("side-parent-001", "side-parent"),
  ep("S02E001", "main"),
  ep("legacy-001", "legacy"),
  ep("S01E001", "main"),
];

describe("buildSections", () => {
  it("groups seasons in episode order, then side stories, then practice; hides placement", () => {
    const s = buildSections(all);
    expect(s.map((x) => x.key)).toEqual(["season-1", "season-2", "side", "practice"]);
    expect(s[0].episodes.map((e) => e.id)).toEqual(["S01E001", "S01E002", "S01E010"]);
    expect(s[0].subtitle).toBe("언니 결혼식");
    expect(s[3].episodes.map((e) => e.id)).toEqual(["legacy-001", "legacy-002"]);
    expect(s.flatMap((x) => x.episodes).some((e) => e.series === "placement")).toBe(false);
  });

  it("drops empty sections", () => {
    expect(buildSections([ep("legacy-001", "legacy")]).map((x) => x.key)).toEqual(["practice"]);
  });
});

describe("upNext", () => {
  it("picks the first unread season episode, then side stories, never practice", () => {
    const s = buildSections(all);
    expect(upNext(s, new Set())?.id).toBe("S01E001");
    expect(upNext(s, new Set(["S01E001"]))?.id).toBe("S01E002");
    const allStory = new Set(["S01E001", "S01E002", "S01E010", "S02E001"]);
    expect(upNext(s, allStory)?.id).toBe("side-parent-001");
    expect(upNext(s, new Set([...allStory, "side-parent-001"]))).toBeUndefined();
  });
});

describe("mainPosition", () => {
  it("parses season and episode numbers", () => {
    expect(mainPosition("S01E005")).toEqual({ season: 1, episode: 5 });
    expect(mainPosition("legacy-001")).toBeNull();
  });
});
