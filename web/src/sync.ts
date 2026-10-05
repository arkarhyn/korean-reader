import { db as defaultDb, type ReaderDB } from "./db";
import { saveData, type PlacementData } from "./placement";
import { saveSets, type WordSet } from "./wordSets";
import type { Device, EventType, QueuedEvent, SyncPull } from "./types";

// Events go to IndexedDB first, always; the server only ever sees them via sync().
// Server dedupes on event id, so a retried batch can never land twice.

const BATCH = 200;
const INTERVAL_MS = 5 * 60 * 1000;
const TIMEOUT_MS = 15_000;

export type SyncStatus = { syncing: boolean; lastSync: string | null; error: string | null };

export function detectDevice(ua = navigator.userAgent, touch = navigator.maxTouchPoints): Device {
  // iPadOS reports a Mac UA; touch support gives it away.
  return /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && touch > 1) ? "iphone" : "laptop";
}

export function createSync(db: ReaderDB, fetchFn: typeof fetch = (...a) => fetch(...a), base = "") {
  let status: SyncStatus = { syncing: false, lastSync: null, error: null };
  const listeners = new Set<() => void>();
  let inflight: Promise<boolean> | null = null;
  const device = detectDevice();

  function setStatus(patch: Partial<SyncStatus>) {
    status = { ...status, ...patch };
    listeners.forEach((l) => l());
  }

  async function call(path: string, init?: RequestInit) {
    const res = await fetchFn(base + path, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
    return res.json();
  }

  async function push() {
    for (;;) {
      const batch = await db.queue.orderBy("ts").limit(BATCH).toArray();
      if (batch.length === 0) return;
      const { accepted, duplicate } = (await call("/api/events/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
      })) as { accepted: string[]; duplicate: string[] };
      await db.queue.bulkDelete([...accepted, ...duplicate]);
      if (batch.length < BATCH) return;
    }
  }

  async function pull() {
    const since = (await db.meta.get("cursor"))?.value;
    const data = (await call(`/api/sync/pull${since ? `?since=${encodeURIComponent(since)}` : ""}`)) as SyncPull;
    await db.transaction("rw", [db.episodes, db.lexemeStates, db.progress, db.meta, db.reviewItems], async () => {
      await db.episodes.bulkPut(data.episodes);
      await db.lexemeStates.bulkPut(data.lexeme_states);
      if (data.review_items) {
        await db.reviewItems.clear();
        await db.reviewItems.bulkPut(data.review_items.map((r, order) => ({ ...r, order })));
      }
      // Read marks from other devices; a mark already on this device keeps its own time.
      for (const c of data.completed ?? []) if (!(await db.progress.get(c.episode_id))) await db.progress.put(c);
      await db.meta.put({ key: "cursor", value: data.server_time });
    });
  }

  // Best effort: placement items + status cached for offline use; never fails a sync.
  async function refreshPlacement() {
    try {
      await saveData(db, (await call("/api/placement")) as PlacementData);
    } catch {
      /* keep the cached copy */
    }
  }

  async function refreshWordSets() {
    try {
      await saveSets(db, (await call("/api/word-sets")) as WordSet[]);
    } catch {
      /* keep the cached copy */
    }
  }

  async function run(): Promise<boolean> {
    setStatus({ syncing: true });
    try {
      await push();
      await pull();
      await refreshPlacement();
      await refreshWordSets();
      const now = new Date().toISOString();
      await db.meta.put({ key: "lastSync", value: now });
      setStatus({ syncing: false, lastSync: now, error: null });
      return true;
    } catch (err) {
      setStatus({ syncing: false, error: err instanceof Error ? err.message : String(err) });
      return false;
    }
  }

  /** Push queued events, then pull changes. Concurrent callers share one run. */
  function sync(): Promise<boolean> {
    inflight ??= run().finally(() => (inflight = null));
    return inflight;
  }

  let flushTimer: ReturnType<typeof setTimeout> | undefined;

  async function logEvent(type: EventType, payload: Record<string, unknown> = {}): Promise<QueuedEvent> {
    const ev: QueuedEvent = { id: crypto.randomUUID(), ts: new Date().toISOString(), device, type, payload };
    await db.queue.add(ev);
    // Opportunistic flush shortly after activity; failures just leave the queue for later.
    clearTimeout(flushTimer);
    if (navigator.onLine) flushTimer = setTimeout(() => void sync(), 3000);
    return ev;
  }

  /** Triggers (SPEC 9): app open, foreground, back online, every 5 min. Returns a stop function. */
  function start(): () => void {
    void db.meta.get("lastSync").then((m) => m && !status.lastSync && setStatus({ lastSync: m.value }));
    void sync();
    const onVisible = () => document.visibilityState === "visible" && void sync();
    const onOnline = () => void sync();
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("online", onOnline);
    const timer = setInterval(() => void sync(), INTERVAL_MS);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("online", onOnline);
      clearInterval(timer);
    };
  }

  return {
    sync,
    logEvent,
    request: call,
    start,
    getStatus: () => status,
    subscribe(l: () => void) {
      listeners.add(l);
      return () => void listeners.delete(l);
    },
  };
}

export const syncer = createSync(defaultDb);
