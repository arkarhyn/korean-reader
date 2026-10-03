import { describe, expect, it } from "vitest";
import { segment, sentenceAt } from "./segments";

describe("segment", () => {
  it("extends a content token over its endings up to the word boundary", () => {
    const ko = "강아지를 키우고 싶었어요.";
    const segs = segment(ko, [
      { s: 0, e: 3, lex: 1 },
      { s: 3, e: 4, g: "G.X" },
      { s: 5, e: 7, lex: 2 },
    ]);
    expect(segs.filter((s) => s.lex).map((s) => [s.text, s.lex])).toEqual([
      ["강아지를", 1],
      ["키우고", 2],
    ]);
    expect(segs.map((s) => s.text).join("")).toBe(ko);
  });

  it("splits a word holding two content tokens", () => {
    const segs = segment("산책시킬게요", [
      { s: 0, e: 2, lex: 1 },
      { s: 2, e: 4, lex: 2 },
    ]);
    expect(segs.map((s) => s.text)).toEqual(["산책", "시킬게요"]);
  });

  it("stops at quotes and punctuation", () => {
    const segs = segment("'초코'라고", [{ s: 1, e: 3, lex: 9 }]);
    expect(segs.find((s) => s.lex)?.text).toBe("초코");
  });
});

describe("sentenceAt", () => {
  it("finds the sentence containing an offset", () => {
    const ko = "첫 문장이에요. 두 번째 문장! 세 번째";
    expect(sentenceAt(ko, 10).text).toBe("두 번째 문장!");
    expect(sentenceAt(ko, ko.length - 1).text).toBe("세 번째");
  });

  it("keeps a closing quote with its sentence", () => {
    const ko = '"제가 다 돌볼게요." 아빠는 웃었어요.';
    expect(sentenceAt(ko, 2).text).toBe('"제가 다 돌볼게요."');
  });
});
