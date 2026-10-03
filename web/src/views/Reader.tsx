import { useLiveQuery } from "dexie-react-hooks";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import Questions from "../components/Questions";
import WordPopover from "../components/WordPopover";
import { db } from "../db";
import { segment, sentenceAt } from "../segments";
import { syncer } from "../sync";
import type { Episode, Paragraph, Question } from "../types";

type Active = { para: number; start: number; end: number; lex: number; surface: string; anchor: DOMRect };

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

function EpisodeView({ episode }: { episode: Episode }) {
  const navigate = useNavigate();
  const [active, setActive] = useState<Active | null>(null);
  const [tapped, setTapped] = useState<Set<number>>(new Set());
  const [flagged, setFlagged] = useState<Set<string>>(new Set());
  const [shown, setShown] = useState<Set<number>>(new Set());
  const opened = useRef(false);

  useEffect(() => {
    if (opened.current) return; // StrictMode re-runs effects; log once per visit
    opened.current = true;
    void syncer.logEvent("episode_open", { episode_id: episode.id });
  }, [episode.id]);

  const tap = useCallback(
    (para: number, start: number, end: number, lex: number, surface: string, el: HTMLElement) => {
      setActive((cur) =>
        cur?.para === para && cur.start === start
          ? null
          : { para, start, end, lex, surface, anchor: el.getBoundingClientRect() },
      );
      setTapped((s) => new Set(s).add(lex));
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

  function answer(q: Question, choice: number, ms: number) {
    void syncer.logEvent("question_answer", {
      episode_id: episode.id,
      question_id: q.id,
      choice_idx: choice,
      correct: choice === q.answer_idx,
      ms,
    });
  }

  async function finish() {
    await syncer.logEvent("episode_complete", { episode_id: episode.id, tapped_lexeme_ids: [...tapped] });
    await db.progress.put({ episode_id: episode.id, completed_at: new Date().toISOString() });
    void syncer.sync();
    navigate("/");
  }

  const activeLexeme = active ? episode.lexemes[String(active.lex)] : undefined;
  const activeFlagged =
    !!active && flagged.has(`${active.para}:${sentenceAt(episode.paragraphs[active.para].ko, active.start).start}`);

  return (
    <div className="mx-auto max-w-[36rem] px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-40">
      <nav className="flex items-center justify-between">
        <Link to="/" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          ← Library
        </Link>
        <span className="text-xs text-ink-soft">{episode.id}</span>
      </nav>

      <header className="mt-6 mb-10 text-center">
        <h1 className="font-title text-[28px] leading-snug font-extrabold">{episode.title_ko}</h1>
        <p className="mt-1 text-sm text-ink-soft">{episode.title_en}</p>
      </header>

      <article className="space-y-7">
        {episode.paragraphs.map((p) => (
          <ParagraphView
            key={p.idx}
            p={p}
            active={active?.para === p.idx ? active.start : null}
            tapped={tapped}
            showEn={shown.has(p.idx)}
            onToggleEn={() =>
              setShown((s) => {
                const n = new Set(s);
                if (!n.delete(p.idx)) n.add(p.idx);
                return n;
              })
            }
            onTap={tap}
          />
        ))}
      </article>

      {episode.questions.length > 0 && (
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

      {active && activeLexeme && (
        <WordPopover
          lexeme={activeLexeme}
          surface={active.surface}
          anchor={active.anchor}
          flagged={activeFlagged}
          onFlag={flag}
          onClose={close}
        />
      )}
    </div>
  );
}

type ParaProps = {
  p: Paragraph;
  active: number | null;
  tapped: Set<number>;
  showEn: boolean;
  onToggleEn: () => void;
  onTap: (para: number, start: number, end: number, lex: number, surface: string, el: HTMLElement) => void;
};

function ParagraphView({ p, active, tapped, showEn, onToggleEn, onTap }: ParaProps) {
  const segs = useMemo(() => segment(p.ko, p.tokens), [p.ko, p.tokens]);
  return (
    <div>
      <p className="font-body text-[19px] leading-[2.05] break-keep sm:text-[20px]">
        {segs.map((s) =>
          s.lex === undefined ? (
            <span key={s.start}>{s.text}</span>
          ) : (
            <span
              key={s.start}
              role="button"
              tabIndex={0}
              className={`word ${active === s.start ? "active" : tapped.has(s.lex) ? "tapped" : ""}`}
              onClick={(e) => onTap(p.idx, s.start, s.end, s.lex!, s.text, e.currentTarget)}
              onKeyDown={(e) => e.key === "Enter" && onTap(p.idx, s.start, s.end, s.lex!, s.text, e.currentTarget)}
            >
              {s.text}
            </span>
          ),
        )}
      </p>
      <div className="mt-1 flex justify-end">
        <button
          type="button"
          onClick={onToggleEn}
          aria-pressed={showEn}
          className="min-h-9 rounded-full px-3 text-xs text-ink-soft active:bg-paper-deep"
        >
          {showEn ? "Hide English" : "English"}
        </button>
      </div>
      {showEn && <p className="mt-1 border-l-2 border-rule pl-3 text-[15px] leading-relaxed text-ink-soft">{p.en}</p>}
    </div>
  );
}
