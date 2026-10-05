import type { ReviewItem } from "./types";

// Quick review (SPEC 3.2): optional, short, tap-only. Items arrive from sync already in the
// server's priority order (most at risk first). No counts or totals are ever shown.

export const SESSION_SIZE = 10;

export function pickSession(items: ReviewItem[], n = SESSION_SIZE): ReviewItem[] {
  return [...items].sort((a, b) => (a.order ?? 0) - (b.order ?? 0)).slice(0, n);
}

/** Split the context sentence around the reviewed word. */
export function splitSentence(it: Pick<ReviewItem, "sentence_ko" | "start" | "end">): [string, string, string] {
  const { sentence_ko: s, start, end } = it;
  return [s.slice(0, start), s.slice(start, end), s.slice(end)];
}
