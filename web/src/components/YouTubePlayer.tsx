import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import { PlaybackClock } from "../playbackClock";

// Minimal YouTube IFrame Player API surface (https://developers.google.com/youtube/iframe_api_reference).
type YTPlayer = {
  playVideo(): void;
  pauseVideo(): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  getPlayerState(): number;
  getPlaybackRate(): number;
  setPlaybackRate(rate: number): void;
  destroy(): void;
};
type YTNamespace = {
  Player: new (
    el: HTMLElement,
    opts: {
      videoId: string;
      playerVars?: Record<string, number | string>;
      events?: {
        onReady?: () => void;
        onStateChange?: (e: { data: number }) => void;
        onPlaybackRateChange?: (e: { data: number }) => void;
      };
    },
  ) => YTPlayer;
};

declare global {
  interface Window {
    YT?: YTNamespace;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let apiPromise: Promise<YTNamespace> | null = null;

/** Load the IFrame API script once per page. */
function loadApi(): Promise<YTNamespace> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  apiPromise ??= new Promise((resolve) => {
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      prev?.();
      resolve(window.YT!);
    };
    const s = document.createElement("script");
    s.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(s);
  });
  return apiPromise;
}

export const PLAYING = 1;

export type PlayerHandle = {
  /** Current position (media ms), extrapolated between the iframe's time reports. */
  timeMs(): number | null;
  /** Actual playback rate (1 until the player is ready). */
  rate(): number;
  seekMs(ms: number): void;
  play(): void;
  pause(): void;
  playing(): boolean;
};

type Props = {
  videoId: string;
  startMs: number;
  endMs: number;
  /** Fires when the video reaches the part's end. */
  onEnded?: () => void;
  /** Playback speed (one of YouTube's rates: 0.25-2 in 0.25 steps). */
  rate?: number;
  /** The speed was changed from YouTube's own settings menu. */
  onRateChange?: (rate: number) => void;
};

/** 16:9 YouTube embed limited to one part's time range (inline on iPhone). */
const YouTubePlayer = forwardRef<PlayerHandle, Props>(function YouTubePlayer(
  { videoId, startMs, endMs, onEnded, rate = 1, onRateChange },
  ref,
) {
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<YTPlayer | null>(null);
  const ready = useRef(false);
  const ended = useRef(onEnded);
  ended.current = onEnded;
  const rateRef = useRef(rate);
  rateRef.current = rate;
  const rateChanged = useRef(onRateChange);
  rateChanged.current = onRateChange;
  const clock = useRef(new PlaybackClock());
  const reportAt = useRef<number | undefined>(undefined);

  // When the player's latest message arrived: getCurrentTime() changes only on these.
  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (/^https:\/\/www\.youtube(-nocookie)?\.com$/.test(e.origin)) reportAt.current = performance.now();
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  useEffect(() => {
    if (ready.current && player.current && player.current.getPlaybackRate() !== rate) player.current.setPlaybackRate(rate);
  }, [rate]);

  useEffect(() => {
    let cancelled = false;
    const el = document.createElement("div");
    host.current?.appendChild(el);
    void loadApi().then((YT) => {
      if (cancelled) return;
      player.current = new YT.Player(el, {
        videoId,
        playerVars: {
          start: Math.floor(startMs / 1000),
          end: Math.ceil(endMs / 1000),
          playsinline: 1,
          rel: 0,
          modestbranding: 1,
          cc_load_policy: 0,
        },
        events: {
          onReady: () => {
            ready.current = true;
            if (rateRef.current !== 1) player.current?.setPlaybackRate(rateRef.current);
          },
          onStateChange: (e) => {
            if (e.data === 0) ended.current?.(); // 0 = ended (the `end` playerVar)
          },
          onPlaybackRateChange: (e) => {
            if (e.data !== rateRef.current) rateChanged.current?.(e.data);
          },
        },
      });
    });
    return () => {
      cancelled = true;
      ready.current = false;
      player.current?.destroy();
      player.current = null;
      el.remove();
    };
  }, [videoId, startMs, endMs]);

  useImperativeHandle(ref, () => ({
    timeMs: () => {
      const p = player.current;
      if (!ready.current || !p) return null;
      const playing = p.getPlayerState() === PLAYING;
      return clock.current.read(p.getCurrentTime() * 1000, performance.now(), p.getPlaybackRate(), playing, reportAt.current);
    },
    rate: () => (ready.current && player.current ? player.current.getPlaybackRate() : 1),
    seekMs: (ms) => {
      if (!ready.current || !player.current) return;
      clock.current.jump(ms, performance.now());
      player.current.seekTo(ms / 1000, true);
      player.current.playVideo();
    },
    play: () => ready.current && player.current?.playVideo(),
    pause: () => ready.current && player.current?.pauseVideo(),
    playing: () => !!(ready.current && player.current && player.current.getPlayerState() === PLAYING),
  }));

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-black [&_iframe]:absolute [&_iframe]:inset-0 [&_iframe]:size-full">
      <div ref={host} className="absolute inset-0" />
    </div>
  );
});

export default YouTubePlayer;
