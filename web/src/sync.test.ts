import "fake-indexeddb/auto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReaderDB } from "./db";
import { createSync, detectDevice } from "./sync";

// In-memory stand-in for the server: idempotent on event id, like POST /api/events/batch.
function fakeServer() {
  const stored = new Map<string, unknown>();
  let down = false;
  let posts = 0;
  let completed: { episode_id: string; completed_at: string }[] = [];
  let reviewItems: unknown[] | undefined;
  let grammar: unknown[] | undefined;
  const fetchFn = vi.fn(async (url: string, init?: RequestInit) => {
    if (down) throw new TypeError("Failed to fetch");
    if (url.startsWith("/api/events/batch")) {
      posts++;
      const { events } = JSON.parse(init!.body as string);
      const accepted: string[] = [];
      const duplicate: string[] = [];
      for (const ev of events) (stored.has(ev.id) ? duplicate : accepted).push(ev.id), stored.set(ev.id, ev);
      return Response.json({ accepted, duplicate });
    }
    if (url.startsWith("/api/sync/pull")) {
      return Response.json({
        server_time: "2026-10-03T00:00:00Z",
        episodes: [],
        lexeme_states: [],
        completed,
        review_items: reviewItems,
        ...(grammar !== undefined ? { grammar } : {}),
      });
    }
    return new Response(null, { status: 404 });
  });
  return {
    fetchFn: fetchFn as unknown as typeof fetch,
    stored,
    setDown: (d: boolean) => (down = d),
    posts: () => posts,
    setCompleted: (c: typeof completed) => (completed = c),
    setReviewItems: (r: unknown[] | undefined) => (reviewItems = r),
    setGrammar: (g: unknown[] | undefined) => (grammar = g),
  };
}

let db: ReaderDB;

beforeEach(() => {
  db = new ReaderDB(`test-${crypto.randomUUID()}`);
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
});

afterEach(async () => {
  vi.useRealTimers();
  db.close();
});

describe("sync", () => {
  it("keeps events queued while offline and delivers them once on reconnect", async () => {
    const server = fakeServer();
    const s = createSync(db, server.fetchFn);
    server.setDown(true);
    await s.logEvent("word_tap", { lexeme_id: 1 });
    await s.logEvent("word_tap", { lexeme_id: 2 });
    expect(await s.sync()).toBe(false);
    expect(await db.queue.count()).toBe(2);
    expect(s.getStatus().error).toMatch(/Failed to fetch/);

    server.setDown(false);
    expect(await s.sync()).toBe(true);
    expect(await db.queue.count()).toBe(0);
    expect(server.stored.size).toBe(2);
    expect((await db.meta.get("cursor"))?.value).toBe("2026-10-03T00:00:00Z");
  });

  it("drops events the server already has (lost response, retried batch)", async () => {
    const server = fakeServer();
    const s = createSync(db, server.fetchFn);
    const ev = await s.logEvent("episode_open", { episode_id: "e1" });
    server.stored.set(ev.id, ev); // server stored it, but the client never saw the reply
    await s.sync();
    expect(await db.queue.count()).toBe(0);
    expect(server.stored.size).toBe(1);
  });

  it("merges read marks from other devices without overwriting local ones", async () => {
    const server = fakeServer();
    const s = createSync(db, server.fetchFn);
    await db.progress.put({ episode_id: "S01E001", completed_at: "2026-10-04T10:00:00Z" });
    server.setCompleted([
      { episode_id: "S01E001", completed_at: "2026-10-01T00:00:00Z" },
      { episode_id: "S01E002", completed_at: "2026-10-04T11:00:00Z" },
    ]);
    await s.sync();
    expect((await db.progress.get("S01E001"))?.completed_at).toBe("2026-10-04T10:00:00Z");
    expect((await db.progress.get("S01E002"))?.completed_at).toBe("2026-10-04T11:00:00Z");
  });

  it("replaces Quick review items on every pull (an older server sends none: keep them)", async () => {
    const server = fakeServer();
    const s = createSync(db, server.fetchFn);
    const item = (id: number) => ({ lexeme_id: id, lemma: "w", pos: "NNG", gloss_en: "g", hanja: null, context_id: 1,
      sentence_ko: "w.", sentence_en: null, start: 0, end: 1, options: ["g", "a", "b"], answer_idx: 0 });
    server.setReviewItems([item(2), item(1)]);
    await s.sync();
    expect((await db.reviewItems.get(2))?.order).toBe(0);
    server.setReviewItems([item(3)]);
    await s.sync();
    expect((await db.reviewItems.toArray()).map((r) => r.lexeme_id)).toEqual([3]);
    server.setReviewItems(undefined);
    await s.sync();
    expect(await db.reviewItems.count()).toBe(1);
  });

  it("replaces grammar points wholesale on every pull (missing = none)", async () => {
    const server = fakeServer();
    const s = createSync(db, server.fetchFn);
    const point = (code: string, state = "new") => ({ code, label_ko: code, htsk_lesson: null, teach_order: 1, state,
      ja_parallel: null, ja_diff_note: null, lesson: null });
    server.setGrammar([point("G.A"), point("G.B")]);
    await s.sync();
    expect((await db.grammar.toArray()).map((g) => g.code).sort()).toEqual(["G.A", "G.B"]);
    server.setGrammar([point("G.B", "introduced")]);
    await s.sync();
    expect(await db.grammar.toArray()).toMatchObject([{ code: "G.B", state: "introduced" }]);
    server.setGrammar(undefined);
    await s.sync();
    expect(await db.grammar.count()).toBe(0);
  });

  it("shares one run between concurrent triggers", async () => {
    const server = fakeServer();
    const s = createSync(db, server.fetchFn);
    await s.logEvent("word_tap", {});
    const [a, b] = await Promise.all([s.sync(), s.sync()]);
    expect(a && b).toBe(true);
    expect(server.posts()).toBe(1);
  });

  it("tags device from the user agent", () => {
    expect(detectDevice("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)", 5)).toBe("iphone");
    expect(detectDevice("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 5)).toBe("iphone");
    expect(detectDevice("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", 0)).toBe("laptop");
  });
});
