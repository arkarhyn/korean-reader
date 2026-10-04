import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { tts } from "../tts";
import type { Lexeme, WordStatus } from "../types";

const POS_LABEL: Record<string, string> = {
  NNG: "noun",
  NNP: "proper noun",
  NNB: "bound noun",
  NR: "numeral",
  NP: "pronoun",
  VV: "verb",
  VA: "adjective",
  VCN: "아니다",
  MAG: "adverb",
  MAJ: "conjunction",
  MM: "determiner",
  IC: "interjection",
};

type Props = {
  lexeme: Lexeme;
  surface: string;
  anchor: DOMRect;
  flagged: boolean;
  onFlag: () => void;
  onClose: () => void;
  /** This word was tapped during this visit (so it can be un-tapped as a mistap). */
  tapped: boolean;
  onMistap: () => void;
  /** Omitted in placement mode, where taps mean "don't know". */
  status?: WordStatus;
  onChangeState: (to: "known" | "learning" | "undo") => void;
};

const isPhone = () => window.matchMedia("(max-width: 639px)").matches;

const pill = "min-h-11 rounded-full border border-rule px-4 text-sm active:opacity-80";

/** Known-status line: offer the change that makes sense for the word's current state. */
function StatusControl({ status, onChange }: { status: WordStatus; onChange: Props["onChangeState"] }) {
  switch (status.kind) {
    case "unknown":
      return (
        <button type="button" onClick={() => onChange("known")} className={`${pill} bg-seal-wash font-bold`}>
          I know this word
        </button>
      );
    case "known":
      return (
        <button type="button" onClick={() => onChange("learning")} className={`${pill} bg-known`}>
          ✓ Known · I forgot this
        </button>
      );
    case "fixed":
      return <span className="px-1 text-sm text-good">✓ Known</span>;
    case "changed":
      return (
        <button type="button" onClick={() => onChange("undo")} aria-pressed className={`${pill} font-bold`}>
          {status.to === "learning" ? "Marked to review · Undo" : "✓ Marked known · Undo"}
        </button>
      );
  }
}

export default function WordPopover(props: Props) {
  const { lexeme, surface, anchor, flagged, onFlag, onClose, tapped, onMistap, status, onChangeState } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const phone = isPhone();

  // Laptop: anchored card under (or above) the word, clamped to the viewport.
  useLayoutEffect(() => {
    if (phone || !ref.current) return;
    const { width, height } = ref.current.getBoundingClientRect();
    const below = anchor.bottom + 8;
    const top = below + height > window.innerHeight - 8 ? anchor.top - height - 8 : below;
    const left = Math.min(Math.max(8, anchor.left + anchor.width / 2 - width / 2), window.innerWidth - width - 8);
    setPos({ top: top + window.scrollY, left: left + window.scrollX });
  }, [anchor, phone]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onDown = (e: PointerEvent) => {
      const t = e.target as HTMLElement;
      if (!ref.current?.contains(t) && !t.closest(".word")) onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [onClose]);

  const placement = phone
    ? "fixed inset-x-0 bottom-0 rounded-t-2xl border-t safe-bottom"
    : "absolute w-80 rounded-xl border";

  return (
    <div
      ref={ref}
      role="dialog"
      aria-label={lexeme.lemma}
      style={phone ? undefined : { top: pos?.top ?? -9999, left: pos?.left ?? 0 }}
      className={`${placement} z-20 border-rule bg-card px-5 pt-4 pb-4 shadow-[0_8px_30px_#0000002e]`}
    >
      {phone && <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-rule" />}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-title text-2xl font-bold">{lexeme.lemma}</span>
            {lexeme.hanja && <span className="font-body text-lg text-accent">{lexeme.hanja}</span>}
          </div>
          <div className="mt-0.5 text-xs text-ink-soft">
            {POS_LABEL[lexeme.pos] ?? lexeme.pos}
            {surface !== lexeme.lemma && <span> · {surface}</span>}
          </div>
        </div>
        {tts.available() && (
          <button
            type="button"
            onClick={() => tts.speak(lexeme.lemma)}
            aria-label="Play pronunciation"
            className="flex size-11 shrink-0 items-center justify-center rounded-full border border-rule text-lg active:bg-paper-deep"
          >
            🔊
          </button>
        )}
      </div>

      <dl className="mt-3 space-y-1.5 text-[15px]">
        <div className="flex gap-3">
          <dt className="w-6 shrink-0 text-xs leading-6 text-ink-soft">EN</dt>
          <dd>{lexeme.gloss_en || <span className="text-ink-soft italic">no dictionary entry</span>}</dd>
        </div>
        {lexeme.gloss_ja && (
          <div className="flex gap-3">
            <dt className="w-6 shrink-0 text-xs leading-6 text-ink-soft">JP</dt>
            <dd lang="ja">{lexeme.gloss_ja}</dd>
          </div>
        )}
      </dl>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {status && <StatusControl status={status} onChange={onChangeState} />}
        {tapped && (
          <button
            type="button"
            onClick={onMistap}
            className="min-h-11 rounded-full px-3 text-xs text-ink-soft active:bg-paper-deep"
          >
            Tapped by mistake
          </button>
        )}
        <button
          type="button"
          onClick={onFlag}
          disabled={flagged}
          className="ml-auto min-h-11 rounded-full px-3 text-xs text-ink-soft active:bg-paper-deep disabled:text-good"
        >
          {flagged ? "✓ Sentence flagged" : "This sentence sounds off"}
        </button>
      </div>
    </div>
  );
}
