import { describe, expect, it } from "vitest";
import { diff, isKnown, type SetItem } from "./wordSets";

const item = (ids: number[], known = false): SetItem => ({ ko: "x", en: "x", lexeme_ids: ids, known });

describe("isKnown", () => {
  it("uses local states over a stale server flag", () => {
    expect(isKnown(item([1]), new Map([[1, "known"]]))).toBe(true);
    expect(isKnown(item([1], true), new Map([[1, "learning"]]))).toBe(false);
    expect(isKnown(item([1], true), new Map())).toBe(true); // e.g. known through another tag
  });
});

describe("diff", () => {
  it("checked -> known, unchecked known -> learning, untouched -> nothing", () => {
    const items = [item([1]), item([2], true), item([3]), item([4, 5])];
    const states = new Map([
      [2, "known"],
      [4, "known"],
    ]);
    // check item 0 and item 3; uncheck item 1; leave item 2 unchecked
    const d = diff(items, new Set([0, 3]), states);
    expect(d.known.sort()).toEqual([1, 5]); // item 3: only the lexeme not already known
    expect(d.learning).toEqual([2]);
  });

  it("does nothing when the checklist matches the current states", () => {
    const items = [item([1]), item([2], true)];
    expect(diff(items, new Set([1]), new Map([[2, "known"]]))).toEqual({ known: [], learning: [] });
  });
});
