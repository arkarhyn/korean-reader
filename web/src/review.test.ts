import { describe, expect, it } from "vitest";
import { pickSession, SESSION_SIZE, splitSentence } from "./review";
import type { ReviewItem } from "./types";

const item = (id: number): ReviewItem => ({
  lexeme_id: id, lemma: "김치", pos: "NNG", gloss_en: "kimchi", hanja: null, context_id: id,
  sentence_ko: "김치도 좋습니다.", sentence_en: "Kimchi is good too.", start: 0, end: 3,
  options: ["kimchi", "rice", "soup"], answer_idx: 0,
});

describe("quick review", () => {
  it("takes a short session in the server's priority order", () => {
    const items = Array.from({ length: 25 }, (_, i) => item(i));
    expect(pickSession(items).map((i) => i.lexeme_id)).toEqual([...Array(SESSION_SIZE).keys()]);
    expect(pickSession(items.slice(0, 2))).toHaveLength(2);
    // IndexedDB hands rows back by lexeme id; the stored server order wins.
    const stored = [{ ...item(5), order: 1 }, { ...item(9), order: 0 }];
    expect(pickSession(stored).map((i) => i.lexeme_id)).toEqual([9, 5]);
  });

  it("splits the sentence around the word", () => {
    expect(splitSentence(item(1))).toEqual(["", "김치도", " 좋습니다."]);
  });
});
