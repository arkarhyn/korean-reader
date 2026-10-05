import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

// Minimal YouTube IFrame Player API surface (https://developers.google.com/youtube/iframe_api_reference).
type YTPlayer = {
  playVideo(): void;
  pauseVideo(): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  getPlayerState(): number;
  destroy(): void;
};
type YTNamespace = {
  Player: new (
    el: HTMLElement,
    opts: {
      videoId: string;
      playerVars?: Record<string, number | string>;
      events?: { onReady?: () => void; onStateChange?: (e: { data: number }) => void };
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
  timeMs(): number | null;
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
};

/** 16:9 YouTube embed limited to one part's time range (inline on iPhone). */
const YouTubePlayer = forwardRef<PlayerHandle, Props>(function YouTubePlayer({ videoId, startMs, endMs, onEnded }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const player = useRef<YTPlayer | null>(null);
  const ready = useRef(false);
  const ended = useRef(onEnded);
  ended.current = onEnded;

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
          },
          onStateChange: (e) => {
            if (e.data === 0) ended.current?.(); // 0 = ended (the `end` playerVar)
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
    timeMs: () => (ready.current && player.current ? player.current.getCurrentTime() * 1000 : null),
    seekMs: (ms) => {
      if (!ready.current || !player.current) return;
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
