import { useLiveQuery } from "dexie-react-hooks";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { db } from "../db";
import { syncer } from "../sync";
import { setWordState } from "../wordActions";
import { COMMON_ID, diff, isKnown, loadSets, saveSets, type CommonPage, type SetItem, type WordSet } from "../wordSets";

const PAGE = 40;

/** Local lexeme states, live (word-set saves and popover changes show up at once). */
function useStates() {
  return useLiveQuery(async () => new Map((await db.lexemeStates.toArray()).map((s) => [s.lexeme_id, s.state])), []);
}

/** Cached sets; fetched once if this device has never synced them. */
function useSets() {
  const cached = useLiveQuery(() => loadSets(db), []);
  useEffect(() => {
    if (cached !== undefined || !navigator.onLine) return;
    syncer
      .request("/api/word-sets")
      .then((sets) => saveSets(db, sets as WordSet[]))
      .catch(() => {});
  }, [cached]);
  return cached;
}

function Shell({ back, title, sub, children }: { back: string; title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl px-4 pt-[max(1.5rem,env(safe-area-inset-top))] pb-36">
      <Link to={back} className="-ml-2 flex min-h-11 w-fit items-center px-2 text-sm text-ink-soft">
        ← {back === "/" ? "Library" : "Word sets"}
      </Link>
      <h1 className="mt-2 font-title text-3xl font-extrabold tracking-tight">{title}</h1>
      {sub && <p className="mt-1 text-sm text-ink-soft">{sub}</p>}
      <div className="mt-6">{children}</div>
    </div>
  );
}

export function WordSetList() {
  const sets = useSets();
  const states = useStates();

  return (
    <Shell back="/" title="단어 세트" sub="Tap the words you know. The next episodes can use them.">
      <Link
        to={`/words/${COMMON_ID}`}
        className="mb-8 block rounded-xl border border-seal bg-seal-wash px-5 py-4 active:opacity-80"
      >
        <h2 className="font-title text-xl font-bold">자주 쓰는 단어</h2>
        <p className="mt-0.5 text-sm text-ink-soft">Common words, by frequency · {PAGE} at a time (online)</p>
      </Link>
      {sets === undefined ? (
        <p className="text-center text-sm text-ink-soft">Sync once online to load the word sets.</p>
      ) : (
        <ul className="divide-y divide-rule border-y border-rule">
          {sets.map((s) => {
            const n = states ? s.items.filter((it) => isKnown(it, states)).length : 0;
            return (
              <li key={s.id}>
                <Link to={`/words/${s.id}`} className="flex min-h-14 items-center gap-3 px-1 py-3 active:bg-paper-deep">
                  <span className="min-w-0 flex-1">
                    <span className="block font-title text-[17px] font-bold">{s.title_ko}</span>
                    <span className="block text-xs text-ink-soft">{s.title_en}</span>
                  </span>
                  <span className={`shrink-0 text-xs ${n === s.items.length ? "text-good" : "text-ink-soft"}`}>
                    {n} / {s.items.length} known
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Shell>
  );
}

export function WordSetChecklist() {
  const { setId = "" } = useParams();
  const sets = useSets();
  if (setId === COMMON_ID) return <CommonWalk />;
  if (sets === undefined) return null;
  const set = sets.find((s) => s.id === setId);
  if (!set)
    return (
      <Shell back="/words" title="Not found">
        <p className="text-ink-soft">That word set doesn't exist.</p>
      </Shell>
    );
  return (
    <Shell back="/words" title={set.title_ko} sub={set.title_en}>
      <Checklist key={set.id} items={set.items} context={set.id} doneLabel="Save" />
    </Shell>
  );
}

function CommonWalk() {
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<CommonPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(null);
    setError(null);
    syncer
      .request(`/api/word-sets/common?offset=${offset}&limit=${PAGE}`)
      .then((p) => setPage(p as CommonPage))
      .catch(() => setError("Couldn't reach the home server. This list needs a connection."));
  }, [offset]);

  return (
    <Shell back="/words" title="자주 쓰는 단어" sub="Most frequent words you haven't marked yet">
      {error && <p className="text-sm text-ink-soft">{error}</p>}
      {page && page.items.length === 0 && <p className="text-sm text-ink-soft">Nothing left on the list. 👏</p>}
      {page && page.items.length > 0 && (
        <Checklist
          key={offset}
          items={page.items}
          context={COMMON_ID}
          doneLabel="Save & next"
          // Saved words drop off the list, so the next unseen words start at this offset again.
          onSaved={(knownCount) => setOffset((o) => o + page.items.length - knownCount)}
          footer={`${page.total} unmarked words left`}
        />
      )}
    </Shell>
  );
}

type ChecklistProps = {
  items: SetItem[];
  context: string;
  doneLabel: string;
  onSaved?: (knownCount: number) => void;
  footer?: string;
};

function Checklist({ items, context, doneLabel, onSaved, footer }: ChecklistProps) {
  const navigate = useNavigate();
  const states = useStates();
  const [checked, setChecked] = useState<Set<number> | null>(null);
  const [saving, setSaving] = useState(false);

  // Start from the current states, once they've loaded.
  useEffect(() => {
    if (states && checked === null)
      setChecked(new Set(items.flatMap((it, i) => (isKnown(it, states) ? [i] : []))));
  }, [states, checked, items]);

  const changes = useMemo(
    () => (checked && states ? diff(items, checked, states) : { known: [], learning: [] }),
    [items, checked, states],
  );

  if (!checked || !states) return null;

  const toggle = (i: number) =>
    setChecked((c) => {
      const n = new Set(c);
      if (!n.delete(i)) n.add(i);
      return n;
    });

  async function save() {
    setSaving(true);
    const log = syncer.logEvent;
    for (const id of changes.known) await setWordState(db, log, id, "known", { word_set: context });
    for (const id of changes.learning) await setWordState(db, log, id, "learning", { word_set: context });
    // The frequency walk's next page must come after the server has applied these.
    if (onSaved) await syncer.sync();
    else void syncer.sync();
    setSaving(false);
    if (onSaved) onSaved(items.filter((_, i) => checked!.has(i)).length);
    else navigate("/words");
  }

  const nChanges = changes.known.length + changes.learning.length;

  return (
    <>
      <p className="mb-3 text-xs text-ink-soft">
        {checked.size} / {items.length} known
        {footer && <span> · {footer}</span>}
      </p>
      <ul className="grid grid-cols-2 gap-2">
        {items.map((it, i) => {
          const on = checked.has(i);
          return (
            <li key={`${it.ko}-${i}`}>
              <button
                type="button"
                onClick={() => toggle(i)}
                aria-pressed={on}
                className={`flex min-h-14 w-full items-center gap-2 rounded-lg border px-3 py-2 text-left active:opacity-80 ${
                  on ? "border-good bg-known" : "border-rule bg-card"
                }`}
              >
                <span className={`w-4 shrink-0 text-sm ${on ? "text-good" : "text-transparent"}`}>✓</span>
                <span className="min-w-0">
                  <span className="block font-title text-[17px] leading-tight font-bold">{it.ko}</span>
                  <span className="block truncate text-xs text-ink-soft">{it.en}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="fixed inset-x-0 bottom-0 border-t border-rule bg-paper/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => setChecked(new Set(items.map((_, i) => i)))}
            className="min-h-12 rounded-full border border-rule px-5 text-sm active:bg-paper-deep"
          >
            Mark all
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void save()}
            className="min-h-12 rounded-full bg-seal px-7 font-title text-lg font-bold text-card active:opacity-80 disabled:opacity-50"
          >
            {doneLabel}
            {nChanges > 0 && <span className="ml-2 text-sm font-normal">({nChanges})</span>}
          </button>
        </div>
      </div>
    </>
  );
}
