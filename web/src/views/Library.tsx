import { useLiveQuery } from "dexie-react-hooks";
import { useState } from "react";
import { Link } from "react-router";
import SyncChip from "../components/SyncChip";
import { db } from "../db";
import { buildSections, mainPosition, upNext, type Section } from "../library";
import { loadData, loadProgress } from "../placement";
import type { Episode } from "../types";

/** Library hides placement calibration passages (series "placement"). */
export const libraryEpisodes = (eps: Episode[]) => eps.filter((e) => e.series !== "placement");

const REGISTER_LABEL: Record<string, string> = { banmal: "반말", haeyo: "해요체", hasipsio: "합니다체" };
const PRACTICE_OPEN_KEY = "library.practiceOpen";

const pct = (ep: Episode) => (ep.coverage !== null ? `${Math.round(ep.coverage * 100)}%` : "");
const epLabel = (ep: Episode) => {
  const pos = mainPosition(ep.id);
  return pos ? `${pos.episode}화` : null;
};

export default function Library() {
  const episodes = useLiveQuery(async () => libraryEpisodes(await db.episodes.toArray()), []);
  const placement = useLiveQuery(async () => ({ data: await loadData(db), progress: await loadProgress(db) }), []);
  const done = useLiveQuery(async () => new Set((await db.progress.toArray()).map((p) => p.episode_id)), []);

  const sections = episodes ? buildSections(episodes) : [];
  const next = done ? upNext(sections, done) : undefined;

  return (
    <div className="mx-auto max-w-2xl px-4 pt-[max(1.5rem,env(safe-area-inset-top))] pb-10 safe-bottom">
      <header className="mb-8 flex items-center justify-between gap-3">
        <h1 className="font-title text-3xl font-extrabold tracking-tight">읽기</h1>
        <SyncChip />
      </header>

      {placement && !placement.data?.fitted && <PlacementCard resume={placement.progress?.step} />}
      {placement?.progress && placement.data?.fitted && <PlacementCard resume={placement.progress.step} />}

      {episodes === undefined ? null : episodes.length === 0 ? (
        <p className="mt-16 text-center text-ink-soft">
          No episodes yet. Connect to the home server and tap sync.
        </p>
      ) : (
        <>
          {next && <UpNext ep={next} />}
          <div className="space-y-10">
            {sections.map((s) => (
              <SectionList key={s.key} section={s} read={done ?? new Set()} nextId={next?.id} />
            ))}
          </div>
        </>
      )}

      {placement?.data?.fitted && !placement.progress && (
        <p className="mt-12 text-center">
          <Link to="/placement" className="text-xs text-ink-soft underline">
            Redo placement
          </Link>
        </p>
      )}
    </div>
  );
}

function UpNext({ ep }: { ep: Episode }) {
  const label = epLabel(ep);
  return (
    <Link
      to={`/read/${ep.id}`}
      className="mb-10 block rounded-xl border border-seal bg-seal-wash px-5 py-5 active:opacity-80"
    >
      <p className="text-xs font-bold tracking-wide text-seal">다음 · UP NEXT</p>
      <h2 className="mt-2 font-title text-2xl font-bold">
        {label && <span className="mr-2 text-seal">{label}</span>}
        {ep.title_ko}
      </h2>
      <p className="mt-0.5 text-sm text-ink-soft">{ep.title_en}</p>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-soft">
        {ep.coverage !== null && <span>{pct(ep)} known</span>}
        {ep.register_tags.map((r) => (
          <span key={r}>{REGISTER_LABEL[r] ?? r}</span>
        ))}
      </div>
    </Link>
  );
}

function SectionList({ section, read, nextId }: { section: Section; read: Set<string>; nextId?: string }) {
  const [open, setOpen] = useState(() => {
    if (!section.collapsible) return true;
    try {
      return localStorage.getItem(PRACTICE_OPEN_KEY) === "1";
    } catch {
      return false;
    }
  });
  const toggle = () => {
    const v = !open;
    setOpen(v);
    try {
      localStorage.setItem(PRACTICE_OPEN_KEY, v ? "1" : "0");
    } catch {
      /* preference only */
    }
  };
  const readCount = section.episodes.filter((e) => read.has(e.id)).length;

  const heading = (
    <>
      <span className="font-title text-lg font-bold">{section.title}</span>
      {section.subtitle && <span className="ml-2 text-sm text-ink-soft">· {section.subtitle}</span>}
    </>
  );

  return (
    <section>
      <div className="mb-2 flex items-baseline justify-between gap-3 border-b border-rule pb-2">
        {section.collapsible ? (
          <button type="button" onClick={toggle} aria-expanded={open} className="min-h-11 text-left">
            <span className="mr-1.5 inline-block w-3 text-ink-soft">{open ? "▾" : "▸"}</span>
            {heading}
          </button>
        ) : (
          <h2>{heading}</h2>
        )}
        <span className="shrink-0 text-xs text-ink-soft">
          {readCount} / {section.episodes.length} read
        </span>
      </div>
      {open && (
        <ul>
          {section.episodes.map((ep) => (
            <EpisodeRow key={ep.id} ep={ep} read={read.has(ep.id)} next={ep.id === nextId} />
          ))}
        </ul>
      )}
    </section>
  );
}

function EpisodeRow({ ep, read, next }: { ep: Episode; read: boolean; next: boolean }) {
  const label = epLabel(ep);
  return (
    <li>
      <Link
        to={`/read/${ep.id}`}
        className={`flex min-h-14 items-center gap-3 rounded-lg px-2 py-2.5 active:bg-paper-deep ${read ? "opacity-55" : ""}`}
      >
        <span className={`w-8 shrink-0 text-center text-sm ${read ? "text-good" : next ? "font-bold text-seal" : "text-ink-soft"}`}>
          {read ? "✓" : (label?.replace("화", "") ?? "·")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-title text-[17px] font-bold">{ep.title_ko}</span>
          <span className="block truncate text-xs text-ink-soft">{ep.title_en}</span>
        </span>
        <span className="shrink-0 text-xs text-ink-soft">{pct(ep)}</span>
      </Link>
    </li>
  );
}

function PlacementCard({ resume }: { resume?: string }) {
  const [title, sub] =
    resume === "done"
      ? ["배치 테스트 마무리", "Answers saved; tap to finish the fit"]
      : resume
        ? ["배치 테스트 계속하기", "Continue placement where you stopped"]
        : ["배치 테스트", "Start here: placement, about 25 minutes"];
  return (
    <Link
      to="/placement"
      className="mb-6 block rounded-lg border border-seal bg-seal-wash px-4 py-4 active:opacity-80"
    >
      <h2 className="font-title text-xl font-bold text-seal">{title}</h2>
      <p className="mt-0.5 text-sm text-ink-soft">{sub}</p>
    </Link>
  );
}
