import { describe, expect, it } from "vitest";
import { MAX_EXTRAPOLATE_MS, PlaybackClock } from "./playbackClock";

describe("PlaybackClock", () => {
  it("extrapolates between reports at the playback rate", () => {
    const c = new PlaybackClock();
    expect(c.read(10_000, 0, 1, true)).toBe(10_000);
    expect(c.read(10_000, 150, 1, true)).toBe(10_150); // no new report yet
    expect(c.read(10_000, 150, 0.5, true)).toBe(10_150); // rate change keeps the position...
    expect(c.read(10_000, 350, 0.5, true)).toBe(10_250); // ...and continues at half speed
    expect(c.read(10_240, 360, 0.5, true)).toBe(10_240); // a fresh report re-anchors
  });

  it("anchors a new report at its arrival time", () => {
    const c = new PlaybackClock();
    c.read(5_000, 0, 1, true);
    expect(c.read(5_250, 300, 1, true, 260)).toBe(5_290); // arrived 40 ms before this poll
    expect(c.read(5_500, 600, 1, true, 100)).toBe(5_500); // stale arrival time is ignored
  });

  it("holds while paused and restarts from there", () => {
    const c = new PlaybackClock();
    c.read(1_000, 0, 1, true);
    expect(c.read(1_200, 200, 1, false)).toBe(1_200);
    expect(c.read(1_200, 5_000, 1, false)).toBe(1_200);
    expect(c.read(1_200, 5_100, 1, true)).toBe(1_300); // resumed: counts from the last paused read
  });

  it("caps extrapolation and follows a seek", () => {
    const c = new PlaybackClock();
    c.read(0, 0, 1, true);
    expect(c.read(0, 10_000, 1, true)).toBe(MAX_EXTRAPOLATE_MS);
    c.jump(60_000, 10_000);
    expect(c.read(0, 10_100, 1, true)).toBe(60_100); // old time still reported: use the target
  });
});
