import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { ReaderDB } from "./db";
import { buildSections, liveCoverage } from "./library";
import { activeLineAt, fetchPodcasts, loadPart, splitByLines, upNextPart } from "./podcasts";
import { segment } from "./segments";
import type { Episode, Paragraph, PodcastShow } from "./types";

const KO = "반찬이 정말 맛있어요\n김치도 좋아요";
const turn: Paragraph = {
  idx: 0,
  ko: KO,
  en: "",
  tokens: [
    { s: 0, e: 2, lex: 1 },
    { s: 4, e: 6, lex: 2 },
    { s: 12, e: 14, lex: 3 },
  ],
  meta: {
    speaker: "디디",
    start_ms: 0,
    end_ms: 6000,
    lines: [
      { s: 0, start_ms: 0, end_ms: 2900, en: "a" },
      { s: 12, start_ms: 3000, end_ms: 6000, en: "b" },
    ],
  },
};
const second: Paragraph = { ...turn, idx: 1, meta: { ...turn.meta!, lines: [{ s: 0, start_ms: 7000, end_ms: 9000, en: "" }] } };

describe("splitByLines", () => {
  it("puts each word on its own subtitle line and drops the newline", () => {
    const lines = splitByLines(segment(KO, turn.tokens), turn);
    expect(lines.map((l) => l.map((s) => s.text).join(""))).toEqual(["반찬이 정말 맛있어요", "김치도 좋아요"]);
    expect(lines[1].find((s) => s.lex === 3)?.start).toBe(12); // offsets stay paragraph-relative
  });
});

describe("activeLineAt", () => {
  it("is the last line that started", () => {
    expect(activeLineAt(-1, [turn, second])).toBeNull();
    expect(activeLineAt(3500, [turn, second])).toEqual({ para: 0, line: 1 });
    expect(activeLineAt(6500, [turn, second])).toEqual({ para: 0, line: 1 }); // gap keeps the last line
    expect(activeLineAt(7000, [turn, second])).toEqual({ para: 1, line: 0 });
  });
});

const part = (id: string, coverage: number) => ({
  id, part: 1, title_ko: "t", title_en: "t", start_ms: 0, end_ms: 1, coverage, primer: null, primer_id: null,
});
const shows: PodcastShow[] = [
  { id: "dt", title_ko: "", title_en: "", episodes: [
    { order: 1, show_episode: 1, title: "A", video_id: "v", register_tags: [], parts: [part("a1", 0.6), part("a2", 0.7)] },
  ] },
];

describe("upNextPart", () => {
  it("is the easiest unread part", () => {
    expect(upNextPart(shows, new Set())?.part.id).toBe("a2");
    expect(upNextPart(shows, new Set(["a2"]))?.part.id).toBe("a1");
    expect(upNextPart(shows, new Set(["a1", "a2"]))).toBeNull();
  });
});

const episode = (id: string, series: string): Episode => ({
  id, series, title_ko: id, title_en: id, register_tags: [], target_grammar: null, coverage: null,
  updated_at: "2026-10-05T00:00:00Z", paragraphs: [], questions: [], lexemes: {},
});

describe("liveCoverage", () => {
  it("counts content words known on this device or always known", () => {
    const ep = { ...episode("S01E001", "main"), paragraphs: [turn], lexemes: {
      "1": { lemma: "반찬", pos: "NNG", gloss_en: "", gloss_ja: null, hanja: null },
      "2": { lemma: "정말", pos: "MAG", gloss_en: "", gloss_ja: null, hanja: null, counts_known: true },
      "3": { lemma: "김치", pos: "NNG", gloss_en: "", gloss_ja: null, hanja: null },
    } };
    const now = Date.parse("2026-10-05T12:00:00Z");
    const rows = new Map([
      [1, { lexeme_id: 1, state: "known", updated_at: "" }],
      [3, { lexeme_id: 3, state: "learning", updated_at: "", due: "2026-10-04T00:00:00Z" }], // due: not known
    ]);
    expect(liveCoverage(ep, rows, now)).toBeCloseTo(2 / 3);
    rows.set(3, { lexeme_id: 3, state: "learning", updated_at: "", due: "2026-10-09T00:00:00Z" }); // fresh
    expect(liveCoverage(ep, rows, now)).toBe(1);
    expect(liveCoverage(episode("x", "main"), rows, now)).toBeNull();
  });
});

describe("library", () => {
  it("hides podcast parts", () => {
    const ids = buildSections([episode("S01E001", "main"), episode("pod-dt-01-p1", "podcast")])
      .flatMap((s) => s.episodes.map((e) => e.id));
    expect(ids).toEqual(["S01E001"]);
  });
});

describe("network", () => {
  it("caches the list and parts for offline use", async () => {
    const db = new ReaderDB(`test-${crypto.randomUUID()}`);
    const ep = episode("pod-dt-01-p1", "podcast");
    const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    const online: typeof fetch = (input) => ok(String(input).includes("/api/podcasts") ? shows : ep);
    const offline: typeof fetch = () => Promise.reject(new TypeError("offline"));

    expect((await fetchPodcasts(db, online))?.[0].id).toBe("dt");
    expect((await fetchPodcasts(db, offline))?.[0].id).toBe("dt");
    expect((await loadPart(db, ep.id, online))?.id).toBe(ep.id);
    expect((await loadPart(db, ep.id, offline))?.id).toBe(ep.id);
    expect(await loadPart(db, "missing", offline)).toBeNull();
  });
});
