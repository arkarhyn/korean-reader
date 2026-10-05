import { useLiveQuery } from "dexie-react-hooks";
import { useRef, useState } from "react";
import { Link } from "react-router";
import { db } from "../db";
import { pickSession, splitSentence } from "../review";
import { syncer } from "../sync";
import { tts } from "../tts";
import type { ReviewItem } from "../types";

// Quick review: a due word in a sentence you've read, a play button, three meanings.
// Deliberately no counts, totals or "N due" (SPEC 3.2: no backlog UI).
export default function Review() {
  const items = useLiveQuery(() => db.reviewItems.toArray(), []);
  const [session, setSession] = useState<ReviewItem[] | null>(null);
  if (items === undefined) return null;
  const list = session ?? pickSession(items);
  if (session === null && list.length) setSession(list);
  return <Session items={list} />;
}

function Session({ items }: { items: ReviewItem[] }) {
  const [i, setI] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const since = useRef(performance.now());
  const it = items[i];

  async function choose(idx: number) {
    if (picked !== null || !it) return;
    setPicked(idx);
    await syncer.logEvent("review_answer", {
      lexeme_id: it.lexeme_id,
      context_id: it.context_id,
      choice_idx: idx,
      correct: idx === it.answer_idx,
      ms: Math.round(performance.now() - since.current),
    });
    await db.reviewItems.delete(it.lexeme_id); // answered; the next sync brings a fresh list
  }

  function next() {
    setI((n) => n + 1);
    setPicked(null);
    since.current = performance.now();
  }

  return (
    <div className="mx-auto max-w-[36rem] px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-24">
      <nav className="flex items-center justify-between">
        <Link to="/" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          ← Library
        </Link>
        <span className="text-xs text-ink-soft">복습 · quick review</span>
      </nav>

      {!it ? (
        <div className="mt-24 text-center">
          <p className="font-title text-2xl font-bold">다 했어요</p>
          <p className="mt-2 text-sm text-ink-soft">That's it for now. The words will turn up again in your stories.</p>
          <Link
            to="/"
            onClick={() => void syncer.sync()}
            className="mt-8 inline-flex min-h-12 items-center rounded-full bg-seal px-8 font-title text-lg font-bold text-card"
          >
            Back to reading
          </Link>
        </div>
      ) : (
        <ReviewCard key={it.lexeme_id} it={it} picked={picked} onChoose={choose} onNext={next} />
      )}
    </div>
  );
}

type CardProps = { it: ReviewItem; picked: number | null; onChoose: (i: number) => void; onNext: () => void };

function ReviewCard({ it, picked, onChoose, onNext }: CardProps) {
  const [before, word, after] = splitSentence(it);
  const answered = picked !== null;
  return (
    <section className="mt-10">
      <div className="flex items-start gap-3">
        <p className="flex-1 font-body text-[21px] leading-[1.9] break-keep">
          {before}
          <button
            type="button"
            onClick={() => tts.speak(it.lemma)}
            className="rounded bg-seal-wash px-0.5 font-bold text-seal"
          >
            {word}
          </button>
          {after}
        </p>
        <button
          type="button"
          onClick={() => tts.speak(it.sentence_ko)}
          aria-label="Play sentence"
          className="flex size-11 shrink-0 items-center justify-center rounded-full border border-rule text-lg active:bg-paper-deep"
        >
          ▶
        </button>
      </div>

      <p className="mt-6 text-sm text-ink-soft">
        What does <span className="font-bold text-ink">{word}</span> mean here?
      </p>
      <div className="mt-3 grid gap-2">
        {it.options.map((opt, i) => {
          const style = !answered
            ? "border-rule bg-card active:bg-paper-deep"
            : i === it.answer_idx
              ? "border-good bg-card text-good"
              : i === picked
                ? "border-bad bg-card text-bad"
                : "border-rule bg-card opacity-50";
          return (
            <button
              key={i}
              type="button"
              disabled={answered}
              onClick={() => onChoose(i)}
              className={`min-h-12 rounded-lg border px-4 py-2 text-left text-[16px] ${style}`}
            >
              {opt}
            </button>
          );
        })}
      </div>

      {answered && (
        <div className="mt-6 space-y-3">
          <p className="text-[15px]">
            <span className="font-bold">{it.lemma}</span>
            {it.hanja && <span className="ml-2 text-ink-soft">{it.hanja}</span>}
            <span className="ml-2 text-ink-soft">— {it.gloss_en}</span>
          </p>
          {it.sentence_en && (
            <p className="border-l-2 border-rule pl-3 text-[15px] leading-relaxed text-ink-soft">{it.sentence_en}</p>
          )}
          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={onNext}
              className="min-h-12 rounded-full bg-seal px-8 font-title text-lg font-bold text-card active:opacity-80"
            >
              다음
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
