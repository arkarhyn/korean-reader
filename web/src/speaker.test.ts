import { describe, expect, it } from "vitest";
import { speakerLabelEnd } from "./views/Reader";

describe("speakerLabelEnd", () => {
  it("finds a '화자: ' label at the start of a dialogue line", () => {
    expect(speakerLabelEnd("어머니: 이선 씨, 왔어?")).toBe("어머니: ".length);
    expect(speakerLabelEnd("이메일: 그 주말에")).toBe(5);
  });
  it("ignores narration and colons later in the line", () => {
    expect(speakerLabelEnd("일요일 오후, 이선은 갔다.")).toBe(0);
    expect(speakerLabelEnd("그는 말했다: 안녕")).toBe(0);
  });
});

describe("speakerColor", () => {
  it("gives each character a fixed color and unknown labels a neutral one", async () => {
    const { speakerColor } = await import("./speakers");
    expect(speakerColor("어머니: ")).toBe("var(--spk-3)");
    expect(speakerColor("엄마:")).toBe(speakerColor("어머니: "));
    expect(speakerColor("이선: ")).not.toBe(speakerColor("서윤: "));
    expect(speakerColor("이메일: ")).toBe("var(--ink-soft)");
  });
});
