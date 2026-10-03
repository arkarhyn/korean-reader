import { useRef, useState } from "react";
import type { Question } from "../types";

type Props = {
  questions: Question[];
  onAnswer: (q: Question, choiceIdx: number, ms: number) => void;
};

// Tap-only; an answer locks the question (first answer is the one that counts).
export default function Questions({ questions, onAnswer }: Props) {
  const [chosen, setChosen] = useState<Record<number, number>>({});
  const since = useRef(performance.now());

  function choose(q: Question, i: number) {
    if (q.id in chosen) return;
    const now = performance.now();
    onAnswer(q, i, Math.round(now - since.current));
    since.current = now;
    setChosen((c) => ({ ...c, [q.id]: i }));
  }

  return (
    <ol className="space-y-8">
      {questions.map((q, n) => {
        const picked = chosen[q.id];
        const answered = picked !== undefined;
        return (
          <li key={q.id}>
            <p className="font-body text-lg leading-relaxed">
              <span className="mr-2 text-accent">{n + 1}.</span>
              {q.prompt_ko}
            </p>
            <p className="mt-1 text-sm text-ink-soft">{q.prompt_en}</p>
            <div className="mt-3 grid gap-2">
              {q.options.map((opt, i) => {
                const state = !answered
                  ? "border-rule bg-card active:bg-paper-deep"
                  : i === q.answer_idx
                    ? "border-good bg-card text-good"
                    : i === picked
                      ? "border-bad bg-card text-bad"
                      : "border-rule bg-card opacity-50";
                return (
                  <button
                    key={i}
                    type="button"
                    disabled={answered}
                    onClick={() => choose(q, i)}
                    className={`min-h-12 rounded-lg border px-4 py-2 text-left font-body text-[17px] ${state}`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
