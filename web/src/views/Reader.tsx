import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import Questions from "../components/Questions";
import WordPopover from "../components/WordPopover";
import WordSpans from "../components/WordSpans";
import { db } from "../db";
import { readerKey, spokenText, step } from "../readAloud";
import { segment } from "../segments";
import { speakerColor } from "../speakers";
import { syncer } from "../sync";
import { tts } from "../tts";
import type { Episode, Paragraph, Question } from "../types";
import { type OnTap, useWordTaps } from "../useWordTaps";

const HIGHLIGHT_KEY = "reader.highlightKnown";

export function loadHighlight(): boolean {
  try {
    return localStorage.getItem(HIGHLIGHT_KEY) !== "0";
  } catch {
    return true;
  }
}

export function saveHighlight(on: boolean) {
  try {
    localStorage.setItem(HIGHLIGHT_KEY, on ? "1" : "0");
  } catch {
    /* preference only */
  }
}

export default function Reader() {
  const { id = "" } = useParams();
  const episode = useLiveQuery(async () => (await db.episodes.get(id)) ?? null, [id]);

  if (episode === undefined) return null;
  if (episode === null)
    return (
      <p className="mt-24 px-4 text-center text-ink-soft">
        This episode isn't on this device yet. <Link to="/" className="text-accent underline">Back</Link>
      </p>
    );
  return <EpisodeView key={episode.id} episode={episode} />;
}

// Placement calibration (Stage 4): taps mean "don't know"; no English, no questions, and
// finishing hands the tapped lexemes back instead of logging episode_complete.
export type PlacementMode = { onDone: (tapped: number[]) => void };

const AUTOPLAY_KEY = "reader.autoplay";

function loadAutoplay(): boolean {
  try {
    return localStorage.getItem(AUTOPLAY_KEY) === "1";
  } catch {
    return false;
  }
}

export function EpisodeView({ episode, placement }: { episode: Episode; placement?: PlacementMode }) {
  const navigate = useNavigate();
  const w = useWordTaps(episode);
  const [shown, setShown] = useState<Set<number>>(new Set());
  const [highlight, setHighlight] = useState(loadHighlight);

  // Read-aloud cursor (DECISIONS 90): one line per step; word taps never move it or replay.
  const [cursor, setCursor] = useState<number | null>(null);
  const [autoplay, setAutoplay] = useState(loadAutoplay);
  const count = episode.paragraphs.length;

  function speakLine(idx: number) {
    const p = episode.paragraphs[idx];
    if (p) tts.speak(spokenText(p.ko, speakerLabelEnd(p.ko)));
  }

  function goTo(idx: number | null, play = autoplay) {
    if (idx === null) return;
    setCursor(idx);
    if (play) speakLine(idx);
    document.getElementById(`para-${idx}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  const move = (delta: number) => goTo(step(cursor, delta, count));
  const replay = () => (cursor === null ? goTo(step(null, 1, count), true) : speakLine(cursor));

  function toggleAutoplay() {
    const on = !autoplay;
    setAutoplay(on);
    try {
      localStorage.setItem(AUTOPLAY_KEY, on ? "1" : "0");
    } catch {
      /* preference only */
    }
  }

  // Laptop: Space / → next, ← back, R replay (not while typing; not in placement).
  const keyRef = useRef<(e: KeyboardEvent) => void>(() => {});
  keyRef.current = (e) => {
    if (placement) return;
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    const action = readerKey(e);
    if (!action) return;
    e.preventDefault();
    if (action === "next") move(1);
    else if (action === "prev") move(-1);
    else replay();
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => keyRef.current(e);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      tts.stop(); // leaving the story stops the voice
    };
  }, []);

  function toggleHighlight() {
    setHighlight((h) => {
      saveHighlight(!h);
      return !h;
    });
  }

  function answer(q: Question, choice: number, ms: number) {
    void syncer.logEvent("question_answer", {
      episode_id: episode.id,
      question_id: q.id,
      choice_idx: choice,
      correct: choice === q.answer_idx,
      ms,
      // What was checked travels with the answer, so a later re-ingest can't change the replay.
      kind: q.kind,
      target_ref: q.target_ref,
    });
  }

  async function finish() {
    if (placement) return placement.onDone([...w.tappedRef.current]);
    await syncer.logEvent("episode_complete", {
      episode_id: episode.id,
      tapped_lexeme_ids: [...w.tappedRef.current],
      lexeme_ids: w.lexIds, // the words this version of the episode contained (hidden SRS reviews)
    });
    await db.progress.put({ episode_id: episode.id, completed_at: new Date().toISOString() });
    void syncer.sync();
    navigate("/");
  }

  const { active } = w;

  return (
    <div className="mx-auto max-w-[36rem] px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-40">
      <nav className="flex items-center justify-between">
        <Link to="/" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          ← Library
        </Link>
        {placement ? (
          <span className="text-xs text-ink-soft">배치 · placement</span>
        ) : (
          <HighlightToggle on={highlight} onToggle={toggleHighlight} />
        )}
      </nav>

      <header className="mt-6 mb-10 text-center">
        <h1 className="font-title text-[28px] leading-snug font-extrabold">{episode.title_ko}</h1>
        <p className="mt-1 text-sm text-ink-soft">{episode.title_en}</p>
        {placement && (
          <p className="mx-auto mt-5 max-w-sm rounded-lg bg-seal-wash px-4 py-3 text-sm leading-relaxed text-ink">
            모르는 단어만 탭하세요. Tap only the words you don't know, then read on.
          </p>
        )}
      </header>

      <article className="space-y-3">
        {episode.paragraphs.map((p) => (
          <ParagraphView
            key={p.idx}
            p={p}
            active={active?.para === p.idx ? active.start : null}
            tapped={w.tapped}
            known={!placement && highlight ? w.known : undefined}
            showEn={shown.has(p.idx)}
            canShowEn={!placement}
            onToggleEn={() =>
              setShown((s) => {
                const n = new Set(s);
                if (!n.delete(p.idx)) n.add(p.idx);
                return n;
              })
            }
            onTap={w.tap}
            current={!placement && cursor === p.idx}
            onMark={placement ? undefined : () => goTo(p.idx)}
          />
        ))}
      </article>

      {!placement && episode.questions.length > 0 && (
        <section className="mt-14">
          <div className="rule-ornament mb-8 text-sm">
            <span>❦</span>
          </div>
          <Questions questions={episode.questions} onAnswer={answer} />
        </section>
      )}

      <div className="mt-12 flex justify-center">
        <button
          type="button"
          onClick={() => void finish()}
          className="min-h-12 rounded-full bg-seal px-8 font-title text-lg font-bold text-card active:opacity-80"
        >
          다 읽었어요
        </button>
      </div>

      {!placement && tts.available() && (
        <div className="fixed inset-x-0 bottom-0 z-10 border-t border-rule bg-paper/95 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur">
          <div className="mx-auto flex max-w-[36rem] items-center gap-2 px-4 pt-2">
            <button type="button" onClick={() => move(-1)} aria-label="Previous line" className={barBtn}>
              ◀
            </button>
            <button type="button" onClick={replay} aria-label="Play line" className={barBtn}>
              ↻
            </button>
            <button type="button" onClick={() => move(1)} aria-label="Next line" className={barBtn}>
              ▶
            </button>
            <button
              type="button"
              onClick={toggleAutoplay}
              aria-pressed={autoplay}
              className="ml-1 flex min-h-11 items-center gap-2 rounded-full px-2 text-xs text-ink-soft active:bg-paper-deep"
            >
              <span className={`inline-block size-3 rounded-sm border border-rule ${autoplay ? "bg-seal-wash" : ""}`} />
              Autoplay
            </button>
            <span className="ml-auto hidden text-[11px] text-ink-soft sm:inline">Space/→ next · ← back · R replay</span>
          </div>
        </div>
      )}

      {active && w.activeLexeme && (
        <WordPopover
          lexeme={w.activeLexeme}
          surface={active.surface}
          anchor={active.anchor}
          flagged={w.activeFlagged}
          onFlag={w.flag}
          onClose={w.close}
          tapped={w.tapped.has(active.lex)}
          onMistap={() => void w.mistap()}
          status={placement ? undefined : w.statusOf(active.lex)}
          onChangeState={(to) => void w.changeState(to)}
        />
      )}
    </div>
  );
}

const barBtn = "flex size-11 items-center justify-center rounded-full border border-rule text-base active:bg-paper-deep";

export function HighlightToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={on}
      className="flex min-h-11 items-center gap-2 rounded-full px-3 text-xs text-ink-soft active:bg-paper-deep"
    >
      <span className={`inline-block size-3 rounded-sm border border-rule ${on ? "bg-known" : ""}`} />
      Highlight known
    </button>
  );
}

type ParaProps = {
  p: Paragraph;
  active: number | null;
  tapped: Set<number>;
  /** Known lexemes to tint; undefined = highlighting off. */
  known?: Set<number>;
  showEn: boolean;
  canShowEn: boolean;
  onToggleEn: () => void;
  onTap: OnTap;
  /** The read-aloud cursor is on this line. */
  current?: boolean;
  /** Margin marker: move the read-aloud cursor here (absent in placement). */
  onMark?: () => void;
};

/** "화자: 대사" dialogue lines (DECISIONS 71): length of the speaker label incl. ": ", else 0. */
export function speakerLabelEnd(ko: string): number {
  const m = /^[^\s:"']{1,8}: /.exec(ko);
  return m ? m[0].length : 0;
}

export function EnToggle({ shown, onToggle }: { shown: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={shown}
      aria-label={shown ? "Hide English" : "Show English"}
      className={`ml-2 inline-flex min-h-8 items-center rounded-full border px-2 align-middle font-ui text-[11px] leading-none active:bg-paper-deep ${
        shown ? "border-accent text-accent" : "border-rule text-ink-soft"
      }`}
    >
      EN
    </button>
  );
}

function ParagraphView({ p, active, tapped, known, showEn, canShowEn, onToggleEn, onTap, current, onMark }: ParaProps) {
  const segs = useMemo(() => segment(p.ko, p.tokens), [p.ko, p.tokens]);
  const labelEnd = speakerLabelEnd(p.ko);
  const labelColor = labelEnd ? speakerColor(p.ko.slice(0, labelEnd)) : undefined;
  const label = segs.filter((s) => s.start < labelEnd);
  const body = segs.filter((s) => s.start >= labelEnd);
  const text = (
    // Dialogue: hanging indent, so a wrapped line never looks like a new paragraph.
    // Narration: flush left with extra space around it, so it reads as its own beat.
    <div className={labelEnd ? "" : "py-2"}>
      <p
        className="font-body text-[19px] leading-[2.05] break-keep sm:text-[20px]"
        style={labelEnd ? { paddingLeft: "1.75em", textIndent: "-1.75em" } : undefined}
      >
        {label.map((s) => (
          <span key={s.start} className="font-bold" style={{ color: labelColor }}>
            {s.text}
          </span>
        ))}
        <WordSpans segs={body} para={p.idx} active={active} tapped={tapped} known={known} onTap={onTap} />
        {canShowEn && <EnToggle shown={showEn} onToggle={onToggleEn} />}
      </p>
      {canShowEn && showEn && (
        <p className={`mt-0.5 mb-2 border-l-2 border-rule pl-3 text-[15px] leading-relaxed text-ink-soft ${labelEnd ? "ml-8" : ""}`}>
          {p.en}
        </p>
      )}
    </div>
  );
  if (!onMark) return text;
  return (
    <div
      id={`para-${p.idx}`}
      className={`-mx-2 flex gap-1 rounded-md pr-2 transition-colors ${current ? "bg-seal-wash" : ""}`}
    >
      <button
        type="button"
        onClick={onMark}
        aria-label={`Read from line ${p.idx + 1}`}
        aria-current={current}
        className={`mt-[0.55em] flex size-8 shrink-0 items-start justify-center rounded-full font-ui text-sm leading-none active:bg-paper-deep ${
          current ? "text-seal" : "text-rule"
        }`}
      >
        {current ? "▸" : "·"}
      </button>
      <div className="min-w-0 flex-1">{text}</div>
    </div>
  );
}
