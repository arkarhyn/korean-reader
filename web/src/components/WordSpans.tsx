import type { Segment } from "../segments";
import type { OnTap } from "../useWordTaps";

export function wordClass(start: number, lex: number, active: number | null, tapped: Set<number>, known?: Set<number>) {
  if (active === start) return "word active";
  if (tapped.has(lex)) return "word tapped";
  return known?.has(lex) ? "word known" : "word";
}

type Props = {
  segs: Segment[];
  para: number;
  /** Start offset of the active word in this paragraph, if any. */
  active: number | null;
  tapped: Set<number>;
  /** Known lexemes to tint; undefined = highlighting off. */
  known?: Set<number>;
  onTap: OnTap;
};

/** Segments of one paragraph as plain text + tappable words (offsets stay paragraph-relative). */
export default function WordSpans({ segs, para, active, tapped, known, onTap }: Props) {
  return (
    <>
      {segs.map((s) =>
        s.lex === undefined ? (
          <span key={s.start}>{s.text}</span>
        ) : (
          <span
            key={s.start}
            role="button"
            tabIndex={0}
            className={wordClass(s.start, s.lex, active, tapped, known)}
            onClick={(e) => onTap(para, s.start, s.end, s.lex!, s.text, e.currentTarget)}
            onKeyDown={(e) => e.key === "Enter" && onTap(para, s.start, s.end, s.lex!, s.text, e.currentTarget)}
          >
            {s.text}
          </span>
        ),
      )}
    </>
  );
}
