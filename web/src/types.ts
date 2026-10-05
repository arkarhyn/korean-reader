// Mirrors server/app/api/schemas.py.

export type Token = { s: number; e: number; lex?: number; g?: string };

export type Lexeme = {
  lemma: string;
  pos: string;
  gloss_en: string;
  gloss_ja: string | null;
  hanja: string | null;
  /** Known regardless of its own state: a story name, or known under another tag. */
  counts_known?: boolean;
};

export type Question = {
  id: number;
  kind: "comprehension" | "meaning_check" | "grammar_check";
  prompt_ko: string;
  prompt_en: string;
  options: string[];
  answer_idx: number;
  target_ref: string | null;
};

/** A podcast turn's subtitle line: `s` = char offset in the paragraph's `ko`. */
export type TurnLine = { s: number; start_ms: number; end_ms: number; en: string };

/** Podcast turns (Stage 7): speaker + timed subtitle lines. */
export type TurnMeta = { speaker: string; uncertain?: boolean; start_ms: number; end_ms: number; lines: TurnLine[] };

export type Paragraph = { idx: number; ko: string; en: string; tokens: Token[]; meta?: TurnMeta | null };

/** Podcast parts: YouTube video + the part's time range. */
export type Media = {
  kind: "youtube";
  video_id: string;
  start_ms: number;
  end_ms: number;
  show: string;
  order: number;
  show_episode: number | null;
  episode_title: string;
  part: number;
  parts: number;
};

export type Episode = {
  id: string;
  series: string;
  title_ko: string;
  title_en: string;
  register_tags: string[];
  target_grammar: string | null;
  coverage: number | null;
  updated_at: string;
  media?: Media | null;
  paragraphs: Paragraph[];
  questions: Question[];
  lexemes: Record<string, Lexeme>;
};

export type LexemeState = {
  lexeme_id: number;
  state: string;
  updated_at: string;
  /** Hidden SRS: a `learning` word counts as known until this time (retrievability 0.9), due after it. */
  due?: string | null;
};

export type Completed = { episode_id: string; completed_at: string };

/** Quick review (SPEC 3.2): a due word in a stored context sentence, with a 3-option meaning pick. */
export type ReviewItem = {
  lexeme_id: number;
  lemma: string;
  pos: string;
  gloss_en: string;
  hanja: string | null;
  context_id: number;
  sentence_ko: string;
  sentence_en: string | null;
  start: number;
  end: number;
  options: string[];
  answer_idx: number;
  /** Position in the server's priority list (set on sync; IndexedDB returns rows by key). */
  order?: number;
};

export type SyncPull = {
  server_time: string;
  episodes: Episode[];
  lexeme_states: LexemeState[];
  completed?: Completed[]; // read marks from every device
  review_items?: ReviewItem[]; // always the full (short) list
};

export type EventType =
  | "episode_open"
  | "word_tap"
  | "episode_complete"
  | "question_answer"
  | "mine_word"
  | "flag_sentence"
  | "placement_answer"
  | "grammar_drill_answer"
  | "set_state"
  | "word_untap"
  | "review_answer"
  | "primer_request";

/** GET /api/podcasts (Stage 7 Listen tab). */
export type PodcastPart = {
  id: string;
  part: number;
  title_ko: string;
  title_en: string;
  start_ms: number;
  end_ms: number;
  coverage: number | null;
  primer: "requested" | "published" | null;
  primer_id: string | null;
};

export type PodcastEpisode = {
  order: number;
  show_episode: number | null;
  title: string;
  video_id: string;
  register_tags: string[];
  parts: PodcastPart[];
};

export type PodcastShow = { id: string; title_ko: string; title_en: string; episodes: PodcastEpisode[] };

export type Device = "laptop" | "iphone";

export type QueuedEvent = {
  id: string;
  ts: string;
  device: Device;
  type: EventType;
  payload: Record<string, unknown>;
};

/** How the word popover describes a word's known status. */
export type WordStatus =
  | { kind: "unknown" } // offer "I know this word"
  | { kind: "known" } // own state known: offer "I forgot this"
  | { kind: "fixed" } // counts known (story name / other tag): nothing to change
  | { kind: "changed"; to: string }; // changed this visit: offer Undo
