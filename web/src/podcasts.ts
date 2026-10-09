import type { ReaderDB } from "./db";
import type { Segment } from "./segments";
import type { Episode, Paragraph, PodcastPart, PodcastShow } from "./types";

// Podcast parts (Stage 7, DECISIONS 84-88). They are not in the sync pull: the list comes
// from GET /api/podcasts and each part is fetched when opened, then kept in db.episodes
// so the popover, known tint and a re-open without network work like a story.

const CACHE_KEY = "podcasts";
type FetchFn = typeof fetch;
const defaultFetch: FetchFn = (...a) => fetch(...a);

export async function loadPodcasts(db: ReaderDB): Promise<PodcastShow[] | undefined> {
  const raw = (await db.meta.get(CACHE_KEY))?.value;
  return raw ? (JSON.parse(raw) as PodcastShow[]) : undefined;
}

/** Refresh the Listen list from the server; falls back to the cached copy when offline. */
export async function fetchPodcasts(db: ReaderDB, fetchFn: FetchFn = defaultFetch): Promise<PodcastShow[] | undefined> {
  try {
    const res = await fetchFn("/api/podcasts", { signal: AbortSignal.timeout(15_000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const shows = (await res.json()) as PodcastShow[];
    await db.meta.put({ key: CACHE_KEY, value: JSON.stringify(shows) });
    return shows;
  } catch {
    return loadPodcasts(db);
  }
}

/** One part, fresh from the server when possible (stored in db.episodes), else the stored copy. */
export async function loadPart(db: ReaderDB, id: string, fetchFn: FetchFn = defaultFetch): Promise<Episode | null> {
  try {
    const res = await fetchFn(`/api/episodes/${encodeURIComponent(id)}`, { signal: AbortSignal.timeout(15_000) });
    if (res.ok) {
      const ep = (await res.json()) as Episode;
      await db.episodes.put(ep);
      return ep;
    }
  } catch {
    /* offline: use the stored copy */
  }
  return (await db.episodes.get(id)) ?? null;
}

export type LineRef = { para: number; line: number };

/** The subtitle line playing at `ms` (the last line that started at or before it), or null before the first. */
export function activeLineAt(ms: number, paragraphs: Paragraph[]): LineRef | null {
  let found: LineRef | null = null;
  for (const p of paragraphs) {
    const lines = p.meta?.lines ?? [];
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].start_ms > ms) return found;
      found = { para: p.idx, line: i };
    }
  }
  return found;
}

/** Split a turn's segments into its subtitle lines (offsets stay paragraph-relative; newlines dropped). */
export function splitByLines(segs: Segment[], paragraph: Paragraph): Segment[][] {
  const starts = (paragraph.meta?.lines ?? []).map((l) => l.s);
  if (starts.length === 0) return [segs];
  const out: Segment[][] = starts.map(() => []);
  const lineOf = (pos: number) => {
    let i = 0;
    while (i + 1 < starts.length && starts[i + 1] <= pos) i++;
    return i;
  };
  for (const s of segs) {
    if (s.lex !== undefined) {
      out[lineOf(s.start)].push(s);
      continue;
    }
    // Plain text may run across a line break: cut it at each line start.
    let pos = s.start;
    while (pos < s.end) {
      const i = lineOf(pos);
      const end = Math.min(s.end, i + 1 < starts.length ? starts[i + 1] : s.end);
      const text = s.text.slice(pos - s.start, end - s.start).replace(/\n/g, "");
      if (text) out[i].push({ text, start: pos, end });
      pos = end;
    }
  }
  return out;
}

/** Easiest (highest coverage) part not read yet, across all shows. */
export function upNextPart(shows: PodcastShow[], read: Set<string>): { part: PodcastPart; title: string } | null {
  let best: { part: PodcastPart; title: string } | null = null;
  for (const show of shows)
    for (const ep of show.episodes)
      for (const part of ep.parts)
        if (!read.has(part.id) && (best === null || (part.coverage ?? 0) > (best.part.coverage ?? 0)))
          best = { part, title: ep.title };
  return best;
}

export function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// Line-by-line listening: one subtitle line per step, pausing at each line's end.

export type TimedLine = LineRef & { start_ms: number; stop_ms: number };

/** Subtitle lines can end a beat before the voice does: play this much past `end_ms`, never into the next line. */
export const LINE_TAIL_MS = 250;

/** Every subtitle line of the part in order, with where line-by-line playback stops it. */
export function timedLines(paragraphs: Paragraph[]): TimedLine[] {
  const out: TimedLine[] = [];
  for (const p of paragraphs)
    (p.meta?.lines ?? []).forEach((l, i) => out.push({ para: p.idx, line: i, start_ms: l.start_ms, stop_ms: l.end_ms }));
  out.forEach((l, i) => {
    const next = out[i + 1]?.start_ms ?? Infinity;
    l.stop_ms = Math.max(l.stop_ms, Math.min(l.stop_ms + LINE_TAIL_MS, next));
  });
  return out;
}

/** Index of `ref` in the flat line list, or -1. */
export function lineIndex(lines: TimedLine[], ref: LineRef | null): number {
  return ref ? lines.findIndex((l) => l.para === ref.para && l.line === ref.line) : -1;
}

/**
 * While a line plays in line-by-line mode: "pause" once playback reaches its stop point,
 * "rearm" if the video was moved elsewhere (scrubber, timestamp), else "keep".
 */
export function lineCheck(ms: number, armed: TimedLine): "pause" | "rearm" | "keep" {
  if (ms < armed.start_ms - 500 || ms > armed.stop_ms + 1500) return "rearm";
  return ms >= armed.stop_ms ? "pause" : "keep";
}

/** Line to arm when playback (re)starts at `ms`: the one playing, or the next if that one is already done. */
export function lineToArm(lines: TimedLine[], ms: number): number {
  let i = -1;
  while (i + 1 < lines.length && lines[i + 1].start_ms <= ms) i++;
  if (i < 0) return lines.length ? 0 : -1;
  if (ms >= lines[i].stop_ms - 50) return i + 1 < lines.length ? i + 1 : -1;
  return i;
}
