import { useLiveQuery } from "dexie-react-hooks";
import { Link } from "react-router";
import SyncChip from "../components/SyncChip";
import { db } from "../db";
import { loadData, loadProgress } from "../placement";
import type { Episode } from "../types";

/** Library hides placement calibration passages (series "placement"). */
export const libraryEpisodes = (eps: Episode[]) => eps.filter((e) => e.series !== "placement");

const REGISTER_LABEL: Record<string, string> = { banmal: "반말", haeyo: "해요체", hasipsio: "합니다체" };

export default function Library() {
  const episodes = useLiveQuery(async () => libraryEpisodes(await db.episodes.orderBy("id").toArray()), []);
  const placement = useLiveQuery(async () => ({ data: await loadData(db), progress: await loadProgress(db) }), []);
  const done = useLiveQuery(async () => new Set((await db.progress.toArray()).map((p) => p.episode_id)), []);

  return (
    <div className="mx-auto max-w-2xl px-4 pt-[max(1.5rem,env(safe-area-inset-top))] safe-bottom">
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
        <ul className="space-y-3">
          {episodes.map((ep) => (
            <li key={ep.id}>
              <Link
                to={`/read/${ep.id}`}
                className="block rounded-lg border border-rule bg-card px-4 py-4 shadow-[0_1px_0_var(--rule)] active:bg-paper-deep"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="font-title text-xl font-bold">{ep.title_ko}</h2>
                  {done?.has(ep.id) && <span className="shrink-0 text-xs text-good">✓ read</span>}
                </div>
                <p className="mt-0.5 text-sm text-ink-soft">{ep.title_en}</p>
                <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-soft">
                  {ep.coverage !== null && <span>{Math.round(ep.coverage * 100)}% known</span>}
                  {ep.register_tags.map((r) => (
                    <span key={r}>{REGISTER_LABEL[r] ?? r}</span>
                  ))}
                  <span className="text-accent">{ep.series}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {placement?.data?.fitted && !placement.progress && (
        <p className="mt-10 mb-6 text-center">
          <Link to="/placement" className="text-xs text-ink-soft underline">
            Redo placement
          </Link>
        </p>
      )}
    </div>
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
