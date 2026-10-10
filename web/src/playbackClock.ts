// The YouTube iframe only reports its time when a postMessage from the player arrives (a few
// times a second), so getCurrentTime() alone can lag the real position by a few hundred ms.
// Between reports we extrapolate from when the last new value arrived, at the playback rate.

/** Never extrapolate further than this (wall ms) without a fresh report. */
export const MAX_EXTRAPOLATE_MS = 1000;

export class PlaybackClock {
  private raw: number | null = null;
  private base = 0;
  private at = 0;
  private rate = 1;

  /**
   * Estimated position (media ms). `raw` is what the player reports, `now` the wall clock,
   * `reportAt` when the player's latest message arrived (anchors a new value more exactly than `now`).
   */
  read(raw: number, now: number, rate: number, playing: boolean, reportAt?: number): number {
    if (raw !== this.raw) {
      this.raw = raw;
      this.base = raw;
      this.at = reportAt !== undefined && reportAt >= this.at && reportAt <= now ? reportAt : now;
    } else if (rate !== this.rate) {
      this.base = this.estimate(now); // keep the position, continue at the new rate
      this.at = now;
    }
    this.rate = rate;
    if (!playing) {
      // Paused / buffering: hold still, and restart extrapolation from here when playback resumes.
      this.base = raw;
      this.at = now;
      return raw;
    }
    return this.estimate(now);
  }

  /** A seek was requested: count from the target until the player reports a new time. */
  jump(ms: number, now: number) {
    this.base = ms;
    this.at = now;
  }

  private estimate(now: number): number {
    return this.base + Math.min(Math.max(0, now - this.at), MAX_EXTRAPOLATE_MS) * this.rate;
  }
}
