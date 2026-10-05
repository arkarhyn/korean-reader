import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import WordPopover from "../components/WordPopover";
import WordSpans from "../components/WordSpans";
import YouTubePlayer, { type PlayerHandle } from "../components/YouTubePlayer";
import { db } from "../db";
import { activeLineAt, formatMs, loadPart, loadPodcasts, type LineRef, splitByLines } from "../podcasts";
import { segment } from "../segments";
import { speakerColor } from "../speakers";
import { syncer } from "../sync";
import type { Episode, Paragraph } from "../types";
import { type OnTap, useWordTaps } from "../useWordTaps";
import { EnToggle, HighlightToggle, loadHighlight, saveHighlight } from "./Reader";

const FOLLOW_KEY = "listen.follow";

export default function ListenPart() {
  const { id = "" } = useParams();
  const [part, setPart] = useState<Episode | null | undefined>(undefined);

  useEffect(() => {
    let live = true;
    setPart(undefined);
    void loadPart(db, id).then((ep) => live && setPart(ep));
    return () => {
      live = false;
    };
  }, [id]);

  if (part === undefined) return <p className="mt-24 text-center text-ink-soft">Loading…</p>;
  if (part === null || !part.media)
    return (
      <p className="mt-24 px-4 text-center text-ink-soft">
        This part needs a connection the first time. <Link to="/listen" className="text-accent underline">Back</Link>
      </p>
    );
  return <PartView key={part.id} part={part} />;
}

function nextPartId(part: Episode): string | null {
  const m = part.media!;
  return m.part < m.parts ? part.id.replace(/-p\d+$/, `-p${m.part + 1}`) : null;
}

function PartView({ part }: { part: Episode }) {
  const media = part.media!;
  const navigate = useNavigate();
  const w = useWordTaps(part);
  const player = useRef<PlayerHandle>(null);
  const [current, setCurrent] = useState<LineRef | null>(null);
  const [follow, setFollow] = useState(() => {
    try {
      return localStorage.getItem(FOLLOW_KEY) !== "0";
    } catch {
      return true;
    }
  });
  const [highlight, setHighlight] = useState(loadHighlight);
  const [shownEn, setShownEn] = useState<Set<number>>(new Set());
  const [primer, setPrimer] = useState<{ status: string | null; id: string | null }>({ status: null, id: null });
  const [ended, setEnded] = useState(false);

  useEffect(() => {
    void loadPodcasts(db).then((shows) => {
      for (const show of shows ?? [])
        for (const ep of show.episodes)
          for (const p of ep.parts) if (p.id === part.id) setPrimer({ status: p.primer, id: p.primer_id });
    });
  }, [part.id]);

  // Follow the video: highlight the line being spoken (and keep it in view when "follow" is on).
  useEffect(() => {
    const t = window.setInterval(() => {
      const ms = player.current?.timeMs();
      if (ms == null) return;
      const at = activeLineAt(ms, part.paragraphs);
      setCurrent((cur) => (cur?.para === at?.para && cur?.line === at?.line ? cur : at));
    }, 250);
    return () => window.clearInterval(t);
  }, [part.paragraphs]);

  useEffect(() => {
    if (!follow || !current || !player.current?.playing()) return;
    document
      .getElementById(`line-${current.para}-${current.line}`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [current, follow]);

  function toggleFollow() {
    setFollow((f) => {
      try {
        localStorage.setItem(FOLLOW_KEY, f ? "0" : "1");
      } catch {
        /* preference only */
      }
      return !f;
    });
  }

  // Looking a word up pauses the video so the line doesn't run away.
  const tap: OnTap = (...args) => {
    player.current?.pause();
    w.tap(...args);
  };

  async function requestPrimer() {
    if (primer.status) return;
    await syncer.logEvent("primer_request", { episode_id: part.id });
    setPrimer({ status: "requested", id: null });
    void syncer.sync();
  }

  async function finish() {
    await syncer.logEvent("episode_complete", {
      episode_id: part.id,
      tapped_lexeme_ids: [...w.tappedRef.current],
      lexeme_ids: w.lexIds,
    });
    await db.progress.put({ episode_id: part.id, completed_at: new Date().toISOString() });
    void syncer.sync();
    const next = nextPartId(part);
    navigate(next ? `/listen/${next}` : "/listen");
  }

  const next = nextPartId(part);
  const { active } = w;

  return (
    <div className="mx-auto max-w-[40rem] pb-40">
      <div className="sticky top-0 z-10 bg-paper px-4 pt-[max(0.5rem,env(safe-area-inset-top))] pb-2">
        <nav className="flex items-center justify-between">
          <Link to="/listen" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
            ← Listen
          </Link>
          <div className="flex items-center">
            <button
              type="button"
              onClick={toggleFollow}
              aria-pressed={follow}
              className="flex min-h-11 items-center gap-2 rounded-full px-3 text-xs text-ink-soft active:bg-paper-deep"
            >
              <span className={`inline-block size-3 rounded-sm border border-rule ${follow ? "bg-seal-wash" : ""}`} />
              Follow
            </button>
            <HighlightToggle
              on={highlight}
              onToggle={() =>
                setHighlight((h) => {
                  saveHighlight(!h);
                  return !h;
                })
              }
            />
          </div>
        </nav>
        <YouTubePlayer
          ref={player}
          videoId={media.video_id}
          startMs={media.start_ms}
          endMs={media.end_ms}
          onEnded={() => setEnded(true)}
        />
      </div>

      <header className="mt-6 mb-8 px-4 text-center">
        <p className="font-ui text-xs text-ink-soft">
          {media.episode_title} · part {media.part}/{media.parts}
        </p>
        <h1 className="mt-2 font-title text-[24px] leading-snug font-extrabold">{part.title_ko}</h1>
        <p className="mt-1 text-sm text-ink-soft">{part.title_en}</p>
      </header>

      <article className="space-y-5 px-4">
        {part.paragraphs.map((p) => (
          <Turn
            key={p.idx}
            p={p}
            current={current?.para === p.idx ? current.line : null}
            active={active?.para === p.idx ? active.start : null}
            tapped={w.tapped}
            known={highlight ? w.known : undefined}
            showEn={shownEn.has(p.idx)}
            onToggleEn={() =>
              setShownEn((s) => {
                const n = new Set(s);
                if (!n.delete(p.idx)) n.add(p.idx);
                return n;
              })
            }
            onSeek={(ms) => player.current?.seekMs(ms)}
            onTap={tap}
          />
        ))}
      </article>

      <div className="mt-12 flex flex-col items-center gap-4 px-4">
        {ended && next && <p className="text-sm text-ink-soft">This part is over.</p>}
        <button
          type="button"
          onClick={() => void finish()}
          className="min-h-12 rounded-full bg-seal px-8 font-title text-lg font-bold text-card active:opacity-80"
        >
          {next ? "다 들었어요 · 다음 파트" : "다 들었어요"}
        </button>
        {primer.status === "published" && primer.id ? (
          <Link to={`/read/${primer.id}`} className="text-sm text-accent underline">
            Read this part's primer story
          </Link>
        ) : (
          <button
            type="button"
            onClick={() => void requestPrimer()}
            disabled={primer.status === "requested"}
            className="min-h-11 rounded-full border border-rule px-4 text-sm text-ink-soft active:bg-paper-deep disabled:opacity-60"
          >
            {primer.status === "requested"
              ? "Primer requested · comes with the next batch"
              : "프라이머 만들기 · pre-teach this part's words"}
          </button>
        )}
      </div>

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
          status={w.statusOf(active.lex)}
          onChangeState={(to) => void w.changeState(to)}
          canLearn
        />
      )}
    </div>
  );
}

type TurnProps = {
  p: Paragraph;
  /** Index of the line being spoken in this turn, if any. */
  current: number | null;
  active: number | null;
  tapped: Set<number>;
  known?: Set<number>;
  showEn: boolean;
  onToggleEn: () => void;
  onSeek: (ms: number) => void;
  onTap: OnTap;
};

function Turn({ p, current, active, tapped, known, showEn, onToggleEn, onSeek, onTap }: TurnProps) {
  const lines = useMemo(() => splitByLines(segment(p.ko, p.tokens), p), [p]);
  const meta = p.meta;
  const speaker = meta?.speaker ?? "";
  return (
    <div>
      <p className="mb-1 flex items-center font-ui text-sm font-bold" style={{ color: speakerColor(speaker) }}>
        {speaker}
        {meta?.uncertain && (
          <span className="ml-0.5 font-normal text-ink-soft" title="Speaker not certain">
            ?
          </span>
        )}
        <EnToggle shown={showEn} onToggle={onToggleEn} />
      </p>
      <div className="space-y-0.5">
        {lines.map((segs, i) => {
          const line = meta?.lines[i];
          return (
            <div
              key={i}
              id={`line-${p.idx}-${i}`}
              className={`flex items-baseline gap-2 rounded-md px-1 ${current === i ? "bg-seal-wash" : ""}`}
            >
              {line && (
                <button
                  type="button"
                  onClick={() => onSeek(line.start_ms)}
                  aria-label={`Play from ${formatMs(line.start_ms)}`}
                  className="w-10 shrink-0 py-1 text-left font-ui text-[11px] text-ink-soft active:text-accent"
                >
                  {formatMs(line.start_ms)}
                </button>
              )}
              <p className="min-w-0 flex-1 font-body text-[18px] leading-[1.9] break-keep sm:text-[19px]">
                <WordSpans segs={segs} para={p.idx} active={active} tapped={tapped} known={known} onTap={onTap} />
              </p>
            </div>
          );
        })}
      </div>
      {showEn && (
        <p className="mt-1 ml-12 border-l-2 border-rule pl-3 text-[15px] leading-relaxed text-ink-soft">
          {p.en || "(no translation)"}
        </p>
      )}
    </div>
  );
}
