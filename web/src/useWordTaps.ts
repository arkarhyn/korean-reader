import { useLiveQuery } from "dexie-react-hooks";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { db } from "./db";
import { sentenceAt } from "./segments";
import { syncer } from "./sync";
import type { Episode, WordStatus } from "./types";
import { countsKnown, KNOWN_STATES, setWordState, untap } from "./wordActions";

export type Active = { para: number; start: number; end: number; lex: number; surface: string; anchor: DOMRect };
export type OnTap = (para: number, start: number, end: number, lex: number, surface: string, el: HTMLElement) => void;

/**
 * Word taps for one visit to an episode (story Reader and podcast Listen view): the active
 * word + popover, tapped set, "sounds off" flags, 알아요 / I forgot this / Undo, the known
 * tint, and the episode_open event.
 */
export function useWordTaps(episode: Episode) {
  const [active, setActive] = useState<Active | null>(null);
  const [tapped, setTapped] = useState<Set<number>>(new Set());
  const tappedRef = useRef<Set<number>>(new Set()); // read at finish; state can lag a burst of taps
  const [flagged, setFlagged] = useState<Set<string>>(new Set());
  const changedRef = useRef<Map<number, string>>(new Map()); // lexeme -> state before this visit's change
  const [changed, setChanged] = useState<Map<number, string>>(new Map());
  const opened = useRef(false);
  const log = syncer.logEvent;

  const lexIds = useMemo(() => Object.keys(episode.lexemes).map(Number), [episode.lexemes]);
  const rows = useLiveQuery(async () => {
    const found = await db.lexemeStates.bulkGet(lexIds);
    return new Map(found.flatMap((r) => (r ? [[r.lexeme_id, r] as const] : [])));
  }, [lexIds]);
  const states = useMemo(() => new Map([...(rows ?? [])].map(([id, r]) => [id, r.state])), [rows]);
  const known = useMemo(() => {
    const s = new Set<number>();
    for (const id of lexIds) {
      if (countsKnown(rows?.get(id)) || episode.lexemes[String(id)]?.counts_known) s.add(id);
    }
    return s;
  }, [lexIds, rows, episode.lexemes]);

  useEffect(() => {
    if (opened.current) return; // StrictMode re-runs effects; log once per visit
    opened.current = true;
    void syncer.logEvent("episode_open", { episode_id: episode.id });
  }, [episode.id]);

  const tap: OnTap = useCallback(
    (para, start, end, lex, surface, el) => {
      setActive((cur) =>
        cur?.para === para && cur.start === start
          ? null
          : { para, start, end, lex, surface, anchor: el.getBoundingClientRect() },
      );
      tappedRef.current.add(lex);
      setTapped(new Set(tappedRef.current));
      void syncer.logEvent("word_tap", { episode_id: episode.id, paragraph_idx: para, start, end, lexeme_id: lex });
    },
    [episode.id],
  );

  const close = useCallback(() => setActive(null), []);

  function flag() {
    if (!active) return;
    const p = episode.paragraphs[active.para];
    const s = sentenceAt(p.ko, active.start);
    const key = `${active.para}:${s.start}`;
    if (flagged.has(key)) return;
    setFlagged((f) => new Set(f).add(key));
    void syncer.logEvent("flag_sentence", {
      episode_id: episode.id,
      paragraph_idx: active.para,
      start: s.start,
      end: s.end,
      text: s.text,
    });
  }

  async function untapActive() {
    if (!active) return;
    await untap(log, tappedRef.current, episode.id, active);
    setTapped(new Set(tappedRef.current));
  }

  async function mistap() {
    await untapActive();
    setActive(null);
  }

  /** "I know this word" -> known; "I forgot this" / "Learn this" -> learning (due now); Undo -> previous state. */
  async function changeState(to: "known" | "learning" | "undo") {
    if (!active) return;
    const lex = active.lex;
    if (to === "undo") {
      const prev = changedRef.current.get(lex);
      if (prev === undefined) return;
      await setWordState(db, log, lex, prev, { episode_id: episode.id, undo: true });
      changedRef.current.delete(lex);
    } else {
      if (to === "known") await untapActive(); // knowing it means the tap wasn't a lookup
      changedRef.current.set(lex, await setWordState(db, log, lex, to, { episode_id: episode.id }));
      if (to === "known") setActive(null);
    }
    setChanged(new Map(changedRef.current));
  }

  function statusOf(lex: number): WordStatus {
    if (changed.has(lex)) return { kind: "changed", to: states?.get(lex) ?? "" };
    if (KNOWN_STATES.has(states?.get(lex) ?? "")) return { kind: "known" };
    if (episode.lexemes[String(lex)]?.counts_known) return { kind: "fixed" };
    return { kind: "unknown" };
  }

  const activeLexeme = active ? episode.lexemes[String(active.lex)] : undefined;
  const activeFlagged =
    !!active && flagged.has(`${active.para}:${sentenceAt(episode.paragraphs[active.para].ko, active.start).start}`);

  return {
    active, tapped, tappedRef, known, lexIds, states, tap, close, flag, mistap, changeState, statusOf,
    activeLexeme, activeFlagged,
  };
}
