import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { db } from "../db";
import { lessonList, markIntroduced, recordAnswer, score, splitBlank, type DrillAnswers } from "../grammar";
import { syncer } from "../sync";
import { tts } from "../tts";
import type { GrammarDrill, GrammarLesson as Lesson, GrammarPoint, GrammarState } from "../types";

// Stage 8 grammar track: card -> examples -> drills -> done. Tap only; no streaks, no praise.

const STATE_LABEL: Record<GrammarState, string> = {
  new: "new",
  introduced: "introduced",
  practicing: "practicing",
  solid: "solid",
};

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-[36rem] flex-col px-4 pt-[max(1rem,env(safe-area-inset-top))] safe-bottom">
      <nav className="flex items-center justify-between">
        <Link to="/" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          ← Library
        </Link>
        <Link to="/grammar" className="-mr-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          문법
        </Link>
      </nav>
      {children}
    </div>
  );
}

const primary =
  "inline-flex min-h-12 items-center justify-center rounded-full bg-seal px-8 font-title text-lg font-bold text-card active:opacity-80";

function NextButton({ onClick, label = "다음" }: { onClick: () => void; label?: string }) {
  return (
    <div className="mt-auto flex justify-end pt-8 pb-6">
      <button type="button" onClick={onClick} className={primary}>
        {label}
      </button>
    </div>
  );
}

/** /grammar: points that have a lesson, in teach order; tap to (re)do one. */
export function GrammarList() {
  const points = useLiveQuery(() => db.grammar.toArray(), []);
  if (points === undefined) return null;
  const list = lessonList(points);
  return (
    <Shell>
      <header className="mt-6 mb-6">
        <h1 className="font-title text-[28px] font-extrabold">문법</h1>
        <p className="text-sm text-ink-soft">Grammar lessons</p>
      </header>
      {list.length === 0 ? (
        <p className="mt-10 text-center text-ink-soft">No grammar lessons yet. They arrive with the next sync.</p>
      ) : (
        <ul>
          {list.map((p) => (
            <li key={p.code}>
              <Link
                to={`/grammar/${encodeURIComponent(p.code)}`}
                className="flex min-h-14 items-center gap-3 rounded-lg px-2 py-2.5 active:bg-paper-deep"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-title text-[17px] font-bold">{p.label_ko}</span>
                  <span className="block truncate text-xs text-ink-soft">{p.lesson?.title_en}</span>
                </span>
                <span
                  className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] ${
                    p.state === "new" ? "border-seal text-seal" : "border-rule text-ink-soft"
                  }`}
                >
                  {STATE_LABEL[p.state] ?? p.state}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Shell>
  );
}

/** /grammar/:code[?then=episodeId] */
export default function GrammarLesson() {
  const { code = "" } = useParams();
  const [params] = useSearchParams();
  const then = params.get("then");
  const point = useLiveQuery(async () => (await db.grammar.get(code)) ?? null, [code]);
  if (point === undefined) return null;
  if (!point?.lesson) return <Missing code={code} point={point} then={then} />;
  return <Flow key={code} point={point} lesson={point.lesson} then={then} />;
}

function Missing({ code, point, then }: { code: string; point: GrammarPoint | null; then: string | null }) {
  return (
    <Shell>
      <div className="mt-16 text-center">
        <p className="font-title text-[32px] font-bold">{point?.label_ko ?? code}</p>
        {point?.ja_parallel && <p className="mt-2 text-ink-soft">Japanese: {point.ja_parallel}</p>}
        {point?.ja_diff_note && <p className="mt-1 text-sm text-ink-soft">{point.ja_diff_note}</p>}
        <p className="mt-8 text-sm text-ink-soft">No lesson for this point yet.</p>
        <div className="mt-8">
          <Link to={then ? `/read/${then}` : "/"} className={primary}>
            {then ? "Read the episode" : "Back to library"}
          </Link>
        </div>
      </div>
    </Shell>
  );
}

type Step = "card" | "examples" | "drills" | "done";

function Flow({ point, lesson, then }: { point: GrammarPoint; lesson: Lesson; then: string | null }) {
  const [step, setStep] = useState<Step>("card");
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<DrillAnswers>({});
  const [visit, setVisit] = useState(() => crypto.randomUUID());
  const shownAt = useRef(performance.now());
  const completed = useRef<string | null>(null); // visit already logged as complete

  const drills = lesson.drills;
  const result = score(answers, drills.length);

  useEffect(() => {
    if (step !== "done" || completed.current === visit) return;
    completed.current = visit;
    void syncer
      .logEvent("grammar_lesson_complete", { code: lesson.code, correct: result.correct, total: result.total, visit })
      .then(() => markIntroduced(db, lesson.code));
  }, [step, visit, lesson.code, result.correct, result.total]);

  function startDrills() {
    setI(0);
    setAnswers({});
    shownAt.current = performance.now();
    setStep(drills.length ? "drills" : "done");
  }

  function choose(choice: number) {
    const d = drills[i];
    if (!d || i in answers) return;
    setAnswers(recordAnswer(answers, i, choice, d.answer));
    void syncer.logEvent("grammar_drill_answer", {
      code: lesson.code,
      drill_idx: i,
      correct: choice === d.answer,
      ms: Math.round(performance.now() - shownAt.current),
      visit,
    });
  }

  function nextDrill() {
    shownAt.current = performance.now();
    if (i + 1 < drills.length) setI(i + 1);
    else setStep("done");
  }

  function again() {
    setVisit(crypto.randomUUID());
    startDrills();
  }

  const ja = lesson.ja_parallel ?? point.ja_parallel;
  const jaNote = lesson.ja_diff_note ?? point.ja_diff_note;

  if (step === "card")
    return (
      <Shell>
        <p className="mt-6 text-xs tracking-wide text-ink-soft">문법 · {lesson.title_en}</p>
        <h1 className="mt-2 font-title text-[36px] leading-tight font-extrabold break-keep">{point.label_ko}</h1>
        <p className="mt-4 text-[16px] leading-relaxed">{lesson.summary_en}</p>
        {(ja || jaNote) && (
          <div className="mt-5 rounded-lg border border-rule bg-card px-4 py-3 text-[15px] leading-relaxed">
            {ja && (
              <p>
                <span className="text-ink-soft">Japanese: </span>
                <span className="font-bold">{ja}</span>
              </p>
            )}
            {jaNote && <p className="mt-1 text-ink-soft">{jaNote}</p>}
          </div>
        )}
        {lesson.notes.length > 0 && (
          <ul className="mt-5 list-disc space-y-2 pl-5 text-[15px] leading-relaxed">
            {lesson.notes.map((n, k) => (
              <li key={k}>{n}</li>
            ))}
          </ul>
        )}
        <NextButton onClick={() => setStep(lesson.examples.length ? "examples" : "drills")} />
      </Shell>
    );

  if (step === "examples") return <Examples lesson={lesson} onNext={startDrills} />;

  if (step === "drills") {
    const d = drills[i];
    const a = answers[i];
    return (
      <Shell>
        <p className="mt-6 text-center text-xs tracking-wide text-ink-soft">
          {point.label_ko} · {i + 1} / {drills.length}
        </p>
        <DrillCard key={`${visit}:${i}`} drill={d} picked={a?.choice ?? null} onChoose={choose} />
        {a && <NextButton onClick={nextDrill} />}
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="mt-20 text-center">
        <p className="font-title text-[28px] font-bold">{point.label_ko}</p>
        {result.total > 0 && (
          <p className="mt-3 text-lg">
            {result.correct} / {result.total} right
          </p>
        )}
        <div className="mt-10 flex flex-col items-center gap-3">
          <Link to={then ? `/read/${then}` : "/"} onClick={() => void syncer.sync()} className={primary}>
            {then ? "Read the episode" : "Back to library"}
          </Link>
          {drills.length > 0 && (
            <button type="button" onClick={again} className="min-h-11 px-3 text-sm text-ink-soft underline active:opacity-70">
              Review again
            </button>
          )}
        </div>
      </div>
    </Shell>
  );
}

const JA_KEY = "grammar.showJa";

function Examples({ lesson, onNext }: { lesson: Lesson; onNext: () => void }) {
  const [showJa, setShowJa] = useState(() => {
    try {
      return localStorage.getItem(JA_KEY) !== "0";
    } catch {
      return true;
    }
  });
  function toggleJa() {
    const v = !showJa;
    setShowJa(v);
    try {
      localStorage.setItem(JA_KEY, v ? "1" : "0");
    } catch {
      /* preference only */
    }
  }
  return (
    <Shell>
      <div className="mt-6 flex items-center justify-between">
        <p className="text-xs tracking-wide text-ink-soft">예문 · Examples</p>
        <button
          type="button"
          onClick={toggleJa}
          aria-pressed={showJa}
          className="flex min-h-11 items-center gap-2 rounded-full px-3 text-xs text-ink-soft active:bg-paper-deep"
        >
          <span className={`inline-block size-3 rounded-sm border border-rule ${showJa ? "bg-seal-wash" : ""}`} />
          日本語
        </button>
      </div>
      <div className="mt-4 space-y-8">
        {lesson.examples.map((ex, k) => (
          <div key={k}>
            <div className="flex items-start gap-3">
              <p className="flex-1 font-body text-[22px] leading-[1.8] break-keep">{ex.ko}</p>
              <button
                type="button"
                onClick={() => tts.speak(ex.ko)}
                aria-label="Play sentence"
                className="flex size-11 shrink-0 items-center justify-center rounded-full border border-rule text-lg active:bg-paper-deep"
              >
                ▶
              </button>
            </div>
            <p className="mt-1 text-[15px] text-ink-soft">{ex.en}</p>
            {showJa && ex.ja && <p className="mt-0.5 text-[15px] text-ink-soft">{ex.ja}</p>}
          </div>
        ))}
      </div>
      <NextButton onClick={onNext} />
    </Shell>
  );
}

type DrillProps = { drill: GrammarDrill; picked: number | null; onChoose: (i: number) => void };

function DrillCard({ drill, picked, onChoose }: DrillProps) {
  const [showEn, setShowEn] = useState(false);
  const answered = picked !== null;
  const correct = picked === drill.answer;
  const parts = splitBlank(drill.prompt_ko);
  const blank = (
    <span
      className={`mx-0.5 inline-block min-w-[3em] rounded px-1 text-center font-bold ${
        answered && correct ? "bg-seal-wash text-good" : "border-b-2 border-seal bg-seal-wash text-seal"
      }`}
    >
      {answered && correct ? drill.options[drill.answer] : " "}
    </span>
  );
  return (
    <section className="mt-8">
      <p className="text-center font-body text-[23px] leading-[1.9] break-keep">
        {parts ? (
          <>
            {parts[0]}
            {blank}
            {parts[1]}
          </>
        ) : (
          drill.prompt_ko
        )}
      </p>
      <div className="mt-2 text-center">
        {showEn ? (
          <p className="text-sm text-ink-soft">{drill.prompt_en}</p>
        ) : (
          <button type="button" onClick={() => setShowEn(true)} className="min-h-11 px-3 text-xs text-ink-soft underline">
            show English
          </button>
        )}
      </div>
      <div className="mt-6 grid gap-2">
        {drill.options.map((opt, k) => {
          const style = !answered
            ? "border-rule bg-card active:bg-paper-deep"
            : k === drill.answer
              ? "border-good bg-card text-good"
              : k === picked
                ? "border-bad bg-card text-bad"
                : "border-rule bg-card opacity-50";
          return (
            <button
              key={k}
              type="button"
              disabled={answered}
              onClick={() => onChoose(k)}
              className={`min-h-14 rounded-xl border px-4 py-2 text-left font-body text-[18px] ${style}`}
            >
              {opt}
            </button>
          );
        })}
      </div>
      {answered && drill.explain_en && (
        <p className="mt-5 border-l-2 border-rule pl-3 text-[15px] leading-relaxed text-ink-soft">{drill.explain_en}</p>
      )}
    </section>
  );
}
