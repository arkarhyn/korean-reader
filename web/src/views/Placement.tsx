import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { db } from "../db";
import {
  advance,
  back,
  clearProgress,
  fraction,
  loadData,
  loadProgress,
  saveProgress,
  start,
  type PlacementData,
  type PlacementProgress,
} from "../placement";
import { syncer } from "../sync";
import { EpisodeView } from "./Reader";

// Stage 4 placement (SPEC 3.5): grammar check -> vocab yes/no -> calibration passages -> fit.
// Every answer is a placement_answer event; the server derives states from the log.

export default function Placement() {
  const data = useLiveQuery(async () => (await loadData(db)) ?? null, []);
  const progress = useLiveQuery(async () => (await loadProgress(db)) ?? null, []);

  useEffect(() => void syncer.sync(), []);

  if (data === undefined || progress === undefined) return null;
  if (data === null) return <NeedsSync />;
  if (progress === null) return <Intro data={data} />;
  return <Run data={data} progress={progress} />;
}

function Shell({ children, progress, data }: { children: React.ReactNode; progress?: PlacementProgress; data?: PlacementData }) {
  const canBack = progress && data && progress.step !== "done" && (progress.index > 0 || progress.step !== "grammar" || progress.rating);
  return (
    <div className="mx-auto flex min-h-dvh max-w-[36rem] flex-col px-4 pt-[max(1rem,env(safe-area-inset-top))] safe-bottom">
      {progress && data && (
        <div className="fixed inset-x-0 top-0 h-1 bg-paper-deep">
          <div className="h-full bg-seal transition-[width]" style={{ width: `${fraction(progress, data) * 100}%` }} />
        </div>
      )}
      <nav className="flex items-center justify-between">
        <Link to="/" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          ← Library
        </Link>
        {canBack && (
          <button
            type="button"
            onClick={() => void saveProgress(db, back(progress, data))}
            className="-mr-2 min-h-11 px-2 text-sm text-ink-soft"
          >
            Undo
          </button>
        )}
      </nav>
      {children}
    </div>
  );
}

function NeedsSync() {
  const [busy, setBusy] = useState(false);
  return (
    <Shell>
      <p className="mt-24 text-center text-ink-soft">Placement needs one sync with the home server first.</p>
      <div className="mt-6 flex justify-center">
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setBusy(true);
            void syncer.sync().finally(() => setBusy(false));
          }}
          className="min-h-12 rounded-full bg-seal px-8 font-title text-lg font-bold text-card active:opacity-80 disabled:opacity-50"
        >
          {busy ? "동기화 중…" : "Sync now"}
        </button>
      </div>
    </Shell>
  );
}

function Intro({ data }: { data: PlacementData }) {
  return (
    <Shell>
      <header className="mt-10 mb-8 text-center">
        <h1 className="font-title text-[28px] font-extrabold">배치 테스트</h1>
        <p className="mt-1 text-sm text-ink-soft">Placement · about 25 minutes · you can stop and resume</p>
      </header>
      <ol className="space-y-4 rounded-lg border border-rule bg-card px-5 py-5 text-[15px] leading-relaxed">
        <li>
          <b className="font-title">1. 문법</b> — {data.grammar.length} short sentences. Is the grammar clear, or fuzzy?
        </li>
        <li>
          <b className="font-title">2. 단어</b> — {data.vocab.length} words. Do you know it? Some are made up, so only
          say yes if you're sure.
        </li>
        <li>
          <b className="font-title">3. 읽기</b> — {data.calibration.length} short passages. Tap only the words you don't
          know.
        </li>
      </ol>
      {data.fitted && (
        <p className="mt-4 text-center text-sm text-ink-soft">You've placed before; finishing again replaces it.</p>
      )}
      <div className="mt-10 flex justify-center">
        <button
          type="button"
          onClick={() => void saveProgress(db, start(crypto.randomUUID(), new Date().toISOString()))}
          className="min-h-12 rounded-full bg-seal px-10 font-title text-lg font-bold text-card active:opacity-80"
        >
          시작
        </button>
      </div>
    </Shell>
  );
}

function Run({ data, progress }: { data: PlacementData; progress: PlacementProgress }) {
  const shownAt = useRef(performance.now());
  const answered = useRef<string | null>(null); // item already answered: ignore a double tap
  const itemKey = `${progress.attempt_id}:${progress.step}:${progress.index}:${progress.rating ? "r" : ""}`;
  useEffect(() => {
    shownAt.current = performance.now();
    answered.current = null; // also after Undo returns to an answered item
  }, [itemKey]);

  async function answer(payload: Record<string, unknown>, next: PlacementProgress) {
    if (answered.current === itemKey) return;
    answered.current = itemKey;
    const ms = Math.round(performance.now() - shownAt.current);
    await syncer.logEvent("placement_answer", { attempt_id: progress.attempt_id, ms, ...payload });
    await saveProgress(db, next);
  }

  if (progress.step === "grammar") {
    const it = data.grammar[progress.index];
    return (
      <Shell progress={progress} data={data}>
        <Card
          label={`문법 ${progress.index + 1} / ${data.grammar.length}`}
          prompt="문법이 이해돼요? · Is the grammar clear?"
          main={<p className="font-body text-[23px] leading-relaxed break-keep">{it.ko}</p>}
          yes="알겠어요"
          no="애매해요"
          onYes={() => void answer({ section: "grammar", item_id: it.id, got_it: true }, advance(progress, data))}
          onNo={() => void answer({ section: "grammar", item_id: it.id, got_it: false }, advance(progress, data))}
        />
      </Shell>
    );
  }

  if (progress.step === "vocab") {
    const it = data.vocab[progress.index];
    return (
      <Shell progress={progress} data={data}>
        <Card
          label={`단어 ${progress.index + 1} / ${data.vocab.length}`}
          prompt="이 단어를 알아요? · Do you know this word?"
          main={<p className="font-title text-[40px] font-bold">{it.word}</p>}
          yes="알아요"
          no="몰라요"
          onYes={() => void answer({ section: "vocab", item_id: it.id, yes: true }, advance(progress, data))}
          onNo={() => void answer({ section: "vocab", item_id: it.id, yes: false }, advance(progress, data))}
        />
      </Shell>
    );
  }

  if (progress.step === "calibration") {
    const episodeId = data.calibration[progress.index];
    if (progress.rating)
      return (
        <Shell progress={progress} data={data}>
          <Rating
            onRate={(rating) =>
              void answer(
                {
                  section: "calibration",
                  episode_id: episodeId,
                  tapped_lexeme_ids: progress.tapped ?? [],
                  rating,
                  ms: progress.read_ms,
                },
                advance(progress, data),
              )
            }
          />
        </Shell>
      );
    return (
      <>
        <div className="fixed inset-x-0 top-0 z-10 h-1 bg-paper-deep">
          <div className="h-full bg-seal" style={{ width: `${fraction(progress, data) * 100}%` }} />
        </div>
        <CalibrationPassage
          key={episodeId}
          episodeId={episodeId}
          onDone={(tapped) =>
            void saveProgress(db, {
              ...progress,
              rating: true,
              tapped,
              read_ms: Math.round(performance.now() - shownAt.current),
            })
          }
        />
      </>
    );
  }

  return <Done progress={progress} />;
}

function Card(props: {
  label: string;
  prompt: string;
  main: React.ReactNode;
  yes: string;
  no: string;
  onYes: () => void;
  onNo: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col pb-6">
      <p className="mt-4 text-center text-xs tracking-wide text-ink-soft">{props.label}</p>
      <div className="flex flex-1 items-center justify-center px-2 text-center">{props.main}</div>
      <p className="mb-4 text-center text-sm text-ink-soft">{props.prompt}</p>
      <div className="flex gap-3">
        <button
          type="button"
          onClick={props.onNo}
          className="min-h-16 flex-1 rounded-xl border border-rule bg-card font-title text-xl font-bold text-ink-soft active:bg-paper-deep"
        >
          {props.no}
        </button>
        <button
          type="button"
          onClick={props.onYes}
          className="min-h-16 flex-1 rounded-xl border border-seal bg-seal-wash font-title text-xl font-bold text-seal active:opacity-80"
        >
          {props.yes}
        </button>
      </div>
    </div>
  );
}

function Rating({ onRate }: { onRate: (r: number) => void }) {
  const labels = ["거의 몰라요", "조금", "반쯤", "대부분", "다 이해해요"];
  return (
    <div className="mt-16 text-center">
      <p className="font-title text-xl font-bold">얼마나 이해했어요?</p>
      <p className="mt-1 text-sm text-ink-soft">How much of that passage did you understand?</p>
      <div className="mt-8 grid gap-2">
        {labels.map((l, i) => (
          <button
            key={l}
            type="button"
            onClick={() => onRate(i + 1)}
            className="min-h-12 rounded-lg border border-rule bg-card px-4 text-left font-body text-[17px] active:bg-paper-deep"
          >
            <span className="mr-3 text-ink-soft">{i + 1}</span>
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}

function CalibrationPassage({ episodeId, onDone }: { episodeId: string; onDone: (tapped: number[]) => void }) {
  const episode = useLiveQuery(async () => (await db.episodes.get(episodeId)) ?? null, [episodeId]);
  if (episode === undefined) return null;
  if (episode === null) return <NeedsSync />;
  return <EpisodeView episode={episode} placement={{ onDone }} />;
}

type FitSummary = {
  minutes: number;
  known_lexemes: number;
  vocab_edge_rank: number;
  grammar: Record<string, string[]>;
  calibration: { episode_id: string; observed: number; expected: number; interval: [number, number]; ok: boolean }[];
};

function Done({ progress }: { progress: PlacementProgress }) {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<FitSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      if (!progress.done_logged) {
        await syncer.logEvent("placement_answer", { attempt_id: progress.attempt_id, section: "done" });
        await saveProgress(db, { ...progress, done_logged: true });
      }
      if (!(await syncer.sync())) throw new Error("offline");
      setSummary((await syncer.request("/api/placement/fit", { method: "POST" })) as FitSummary);
      await syncer.sync(); // pull the new states + coverage
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void finish();
  });

  return (
    <Shell>
      <header className="mt-10 mb-6 text-center">
        <h1 className="font-title text-[28px] font-extrabold">수고했어요</h1>
        <p className="mt-1 text-sm text-ink-soft">Placement finished</p>
      </header>
      {summary ? (
        <div className="space-y-4 rounded-lg border border-rule bg-card px-5 py-5 text-[15px] leading-relaxed">
          <p>
            About <b>{summary.known_lexemes.toLocaleString()}</b> words marked known (edge around frequency rank{" "}
            {Math.round(summary.vocab_edge_rank).toLocaleString()}).
          </p>
          <p>
            Grammar: {summary.grammar.solid?.length ?? 0} solid, {summary.grammar.practicing?.length ?? 0} practicing,{" "}
            {summary.grammar.new?.length ?? 0} to learn.
          </p>
          <ul className="space-y-1 text-sm text-ink-soft">
            {summary.calibration.map((c) => (
              <li key={c.episode_id}>
                {c.episode_id}: tapped {pct(c.observed)}, model {pct(c.interval[0])}–{pct(c.interval[1])}{" "}
                {c.ok ? "✓" : "✗"}
              </li>
            ))}
          </ul>
          <p className="text-sm text-ink-soft">{summary.minutes} min</p>
        </div>
      ) : error ? (
        <p className="text-center text-ink-soft">
          Your answers are saved. The fit will finish once the home server is reachable.
          <span className="mt-1 block text-xs">({error})</span>
        </p>
      ) : (
        <p className="text-center text-ink-soft">Fitting…</p>
      )}
      <div className="mt-10 flex justify-center gap-3">
        {!summary && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void finish()}
            className="min-h-12 rounded-full border border-rule bg-card px-6 font-title text-lg font-bold active:bg-paper-deep disabled:opacity-50"
          >
            Retry
          </button>
        )}
        {summary && (
          <button
            type="button"
            onClick={() => void clearProgress(db).then(() => navigate("/"))}
            className="min-h-12 rounded-full bg-seal px-8 font-title text-lg font-bold text-card active:opacity-80"
          >
            Library
          </button>
        )}
      </div>
    </Shell>
  );
}

const pct = (x: number) => `${Math.round(x * 100)}%`;
