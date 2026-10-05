import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { db } from "../db";
import { fetchPodcasts, formatMs, loadPodcasts, upNextPart } from "../podcasts";
import type { PodcastPart, PodcastShow } from "../types";

/** Listen tab (Stage 7): podcast episodes split into ~10-minute parts, kept apart from the story Library. */
export default function Listen() {
  const [shows, setShows] = useState<PodcastShow[] | undefined>(undefined);
  const [offline, setOffline] = useState(false);
  const read = useLiveQuery(async () => new Set((await db.progress.toArray()).map((p) => p.episode_id)), []);

  useEffect(() => {
    let live = true;
    void loadPodcasts(db).then((cached) => live && cached && setShows((s) => s ?? cached));
    void fetchPodcasts(db, async (...a) => {
      try {
        return await fetch(...a);
      } catch (e) {
        if (live) setOffline(true);
        throw e;
      }
    }).then((fresh) => live && setShows(fresh ?? []));
    return () => {
      live = false;
    };
  }, []);

  const next = shows && read ? upNextPart(shows, read) : null;

  return (
    <div className="mx-auto max-w-2xl px-4 pt-[max(1rem,env(safe-area-inset-top))] pb-24">
      <nav className="flex items-center justify-between">
        <Link to="/" className="-ml-2 flex min-h-11 items-center px-2 text-sm text-ink-soft">
          ← Library
        </Link>
        {offline && <span className="text-xs text-ink-soft">offline · cached list</span>}
      </nav>

      <header className="mt-6 mb-8">
        <h1 className="font-title text-[28px] font-extrabold">듣기</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Real conversations, read along with the video. Harder than the stories: tap freely.
        </p>
      </header>

      {shows === undefined && <p className="text-ink-soft">Loading…</p>}
      {shows?.length === 0 && <p className="text-ink-soft">No podcasts yet.</p>}

      {next && (
        <Link
          to={`/listen/${next.part.id}`}
          className="mb-10 block rounded-xl border border-rule bg-card px-5 py-4 active:bg-paper-deep"
        >
          <p className="font-ui text-xs tracking-wide text-ink-soft uppercase">Up next · easiest unread part</p>
          <p className="mt-1 font-title text-lg font-bold">{next.part.title_ko}</p>
          <p className="text-sm text-ink-soft">
            {next.part.title_en} · {Math.round((next.part.coverage ?? 0) * 100)}% known
          </p>
        </Link>
      )}

      {shows?.map((show) => (
        <section key={show.id} className="mb-12">
          <h2 className="font-title text-xl font-bold">{show.title_ko}</h2>
          <p className="mb-5 text-sm text-ink-soft">{show.title_en}</p>
          <ol className="space-y-6">
            {show.episodes.map((ep) => (
              <li key={ep.order}>
                <p className="font-body text-[17px] leading-snug">{ep.title}</p>
                {ep.register_tags.includes("banmal") && <p className="text-xs text-accent">반말 episode</p>}
                <ul className="mt-2 divide-y divide-rule border-y border-rule">
                  {ep.parts.map((p) => (
                    <PartRow key={p.id} part={p} read={read?.has(p.id) ?? false} />
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function PartRow({ part, read }: { part: PodcastPart; read: boolean }) {
  return (
    <li>
      <Link
        to={`/listen/${part.id}`}
        className={`flex min-h-12 items-center gap-3 py-2 active:bg-paper-deep ${read ? "opacity-60" : ""}`}
      >
        <span className="w-6 shrink-0 text-center font-ui text-xs text-ink-soft">{read ? "✓" : part.part}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px]">{part.title_ko}</span>
          <span className="block truncate text-xs text-ink-soft">
            {part.title_en} · {formatMs(part.end_ms - part.start_ms)}
          </span>
        </span>
        {part.primer === "published" && <span className="rounded-full bg-seal-wash px-2 text-[11px]">primer</span>}
        <span className="w-10 shrink-0 text-right font-ui text-xs text-ink-soft">
          {Math.round((part.coverage ?? 0) * 100)}%
        </span>
      </Link>
    </li>
  );
}
