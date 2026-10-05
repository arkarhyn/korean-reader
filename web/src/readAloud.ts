// Read-aloud cursor for story passages (DECISIONS 90): one line (paragraph) per step.

/** What is spoken for a line: the text without its "화자: " label. */
export function spokenText(ko: string, labelEnd: number): string {
  return ko.slice(labelEnd).trim();
}

/** Move the cursor by `delta` lines, clamped to the passage; no cursor yet starts at the first line. */
export function step(cursor: number | null, delta: number, count: number): number | null {
  if (count === 0) return null;
  if (cursor === null) return 0;
  return Math.min(count - 1, Math.max(0, cursor + delta));
}

/** Keys the reader handles: Space / → next, ← back, R replay. Null for everything else. */
export function readerKey(e: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey">): "next" | "prev" | "replay" | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null;
  if (e.key === " " || e.key === "ArrowRight") return "next";
  if (e.key === "ArrowLeft") return "prev";
  if (e.key === "r" || e.key === "R") return "replay";
  return null;
}
