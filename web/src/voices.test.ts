import { describe, expect, it } from "vitest";
import { DEFAULT_VOICE, pickVoice, voiceFor } from "./voices";

describe("voiceFor", () => {
  it("gives the main cast their own voice and everyone else the default", () => {
    expect(voiceFor("아버지: ").pitch).toBeLessThan(1);
    expect(voiceFor("서현").pitch).toBeGreaterThan(1);
    expect(voiceFor("엄마: ")).toEqual(voiceFor("어머니"));
    expect(voiceFor("")).toEqual(DEFAULT_VOICE); // narration
    expect(voiceFor("이메일: ")).toEqual(DEFAULT_VOICE); // non-character label
    expect(voiceFor("점원: ")).toEqual(DEFAULT_VOICE); // minor character
  });
});

describe("pickVoice", () => {
  const ko1 = { name: "A", lang: "ko-KR" };
  const ko2 = { name: "B", lang: "ko_KR" };
  const en = { name: "E", lang: "en-US" };
  it("uses the second Korean voice for alt only when there is one", () => {
    expect(pickVoice([en, ko1, ko2], true)).toBe(ko2);
    expect(pickVoice([en, ko1, ko2], false)).toBe(ko1);
    expect(pickVoice([en, ko1], true)).toBe(ko1);
    expect(pickVoice([en], false)).toBeUndefined();
  });

  it("uses the voice picker's choice when this device has it", () => {
    const ko3 = { name: "C", lang: "ko-KR" };
    expect(pickVoice([ko1, ko2, ko3], true, { alt: "C" })).toBe(ko3);
    expect(pickVoice([ko1, ko2, ko3], false, { default: "B", alt: "C" })).toBe(ko2);
    expect(pickVoice([ko1, ko2], true, { alt: "gone" })).toBe(ko2); // missing here -> automatic
  });
});
