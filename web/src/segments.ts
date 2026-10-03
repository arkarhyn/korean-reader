import type { Token } from "./types";

export type Segment = { text: string; start: number; end: number; lex?: number };

// A tap target covers its content token plus the endings glued to it, up to the
// next content token or the end of the word, so 키우고 is one target for 키우다.
const BOUNDARY = /[\s.,!?'"“”‘’…·()[\]{}:;~-]/;

export function segment(ko: string, tokens: Token[]): Segment[] {
  const content = tokens.filter((t) => t.lex !== undefined).sort((a, b) => a.s - b.s);
  const out: Segment[] = [];
  let pos = 0;
  content.forEach((t, i) => {
    if (t.s < pos) return; // overlapping span; keep the earlier target
    if (t.s > pos) out.push({ text: ko.slice(pos, t.s), start: pos, end: t.s });
    const limit = i + 1 < content.length ? content[i + 1].s : ko.length;
    let end = t.e;
    while (end < limit && !BOUNDARY.test(ko[end])) end++;
    out.push({ text: ko.slice(t.s, end), start: t.s, end, lex: t.lex });
    pos = end;
  });
  if (pos < ko.length) out.push({ text: ko.slice(pos), start: pos, end: ko.length });
  return out;
}

/** Sentence containing [start, end) in a paragraph, for "sounds off" flags (SPEC 8). */
export function sentenceAt(ko: string, start: number): { start: number; end: number; text: string } {
  const re = /[^.!?]*[.!?]+["”’']*\s*|[^.!?]+$/g;
  for (const m of ko.matchAll(re)) {
    const s = m.index!;
    const e = s + m[0].length;
    if (start >= s && start < e) return { start: s, end: e, text: m[0].trim() };
  }
  return { start: 0, end: ko.length, text: ko };
}
