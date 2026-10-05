import type { Episode } from "./types";

// Library organization: an "up next" pick plus sections by series.
// Main-series ids look like S01E005; everything else sorts by id.

export type Section = {
  key: string;
  title: string;
  subtitle?: string;
  episodes: Episode[];
  collapsible: boolean;
};

/** Season titles from docs/STORY_BIBLE.md. */
const SEASON_TITLES: Record<number, string> = { 1: "언니 결혼식" };
const SIDE_SERIES = new Set(["side-parent", "side-folk"]);
/** Not story content: placement calibration passages, and podcast parts (Listen tab, Stage 7). */
export const HIDDEN_SERIES = new Set(["placement", "podcast"]);

const MAIN_ID = /^S(\d+)E(\d+)$/;

export function mainPosition(id: string): { season: number; episode: number } | null {
  const m = MAIN_ID.exec(id);
  return m ? { season: Number(m[1]), episode: Number(m[2]) } : null;
}

const byId = (a: Episode, b: Episode) => a.id.localeCompare(b.id, undefined, { numeric: true });

/** Sections in display order; empty sections are dropped. Placement passages never appear. */
export function buildSections(episodes: Episode[]): Section[] {
  const seasons = new Map<number, Episode[]>();
  const side: Episode[] = [];
  const practice: Episode[] = [];
  for (const ep of episodes) {
    if (HIDDEN_SERIES.has(ep.series)) continue;
    const pos = ep.series === "main" ? mainPosition(ep.id) : null;
    if (pos) seasons.set(pos.season, [...(seasons.get(pos.season) ?? []), ep]);
    else if (SIDE_SERIES.has(ep.series)) side.push(ep);
    else practice.push(ep); // legacy, primer, and anything unrecognized
  }
  const sections: Section[] = [...seasons.entries()]
    .sort(([a], [b]) => a - b)
    .map(([season, eps]) => ({
      key: `season-${season}`,
      title: `시즌 ${season}`,
      subtitle: SEASON_TITLES[season],
      episodes: eps.sort(byId),
      collapsible: false,
    }));
  if (side.length) sections.push({ key: "side", title: "곁이야기", subtitle: "Side stories", episodes: side.sort(byId), collapsible: false });
  if (practice.length)
    sections.push({ key: "practice", title: "연습", subtitle: "Practice", episodes: practice.sort(byId), collapsible: true });
  return sections;
}

/** First unread episode: earliest season episode, then side stories. Practice texts are never "next". */
export function upNext(sections: Section[], read: Set<string>): Episode | undefined {
  for (const s of sections) {
    if (s.key === "practice") continue;
    const ep = s.episodes.find((e) => !read.has(e.id));
    if (ep) return ep;
  }
  return undefined;
}
