import { describe, expect, it } from "vitest";
import { readerKey, spokenText, step } from "./readAloud";
import { speakerLabelEnd } from "./views/Reader";

describe("spokenText", () => {
  it("drops the speaker label", () => {
    const ko = "서윤: 엄마, 우리 왔어요.";
    expect(spokenText(ko, speakerLabelEnd(ko))).toBe("엄마, 우리 왔어요.");
    expect(spokenText("토요일 저녁이었다.", 0)).toBe("토요일 저녁이었다.");
  });
});

describe("step", () => {
  it("starts at the first line and clamps", () => {
    expect(step(null, 1, 3)).toBe(0);
    expect(step(0, 1, 3)).toBe(1);
    expect(step(2, 1, 3)).toBe(2);
    expect(step(0, -1, 3)).toBe(0);
    expect(step(null, 1, 0)).toBeNull();
  });
});

describe("readerKey", () => {
  const k = (key: string, mod = false) => readerKey({ key, ctrlKey: mod, metaKey: false, altKey: false });
  it("maps Space/arrows/R and ignores shortcuts", () => {
    expect(k(" ")).toBe("next");
    expect(k("ArrowRight")).toBe("next");
    expect(k("ArrowLeft")).toBe("prev");
    expect(k("r")).toBe("replay");
    expect(k("r", true)).toBeNull();
    expect(k("a")).toBeNull();
  });
});
