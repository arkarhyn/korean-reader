# SYLLABUS_MAP (seed -- build out in a Project design session before Stage 8)

Map only. Do NOT copy HowToStudyKorean text. Columns:
HTSK lesson | grammar code | label (KO) | Japanese parallel | where it differs | Kiwi pattern

Current position: around Lesson 29 (-기 / -(으)ㅁ nominalization).
Lessons 1-28 are verified by the Stage 4 grammar check, not assumed.

## Lessons 1-28 (Stage 4; source of truth: `content/seed/grammar_points.json`)
Drafted by Claude, approved by Austin 2026-10-03. Each row has 2 placement
check sentences (`content/placement/grammar.json`; one check covers
G.EGE/G.HANTE/G.KKE). Kiwi patterns are filled in Stage 8. Left out:
이래로/이내 (L24), 들 (L12), compound verbs (L15); 에게서/한테서 are seeded.

| Lesson | Code | KO | JA | Differs | Kiwi pattern |
|---|---|---|---|---|---|
| 1 | G.TOPIC | 은/는 | は | Close match, incl. contrast use. | — |
| 1 | G.COPULA | 이다 | だ／である | Attaches to the noun and conjugates like a verb (학생이에요). | — |
| 2 | G.SUBJ | 이/가 | が | Close match; 이/가 also marks the complement of 되다/아니다. | — |
| 2 | G.ISSTA | 있다/없다 | ある・いる／ない | No animate/inanimate split; also 'to have'. | — |
| 3 | G.OBJ | 을/를 | を | Used with 좋아하다 where Japanese uses が (好きだ). | — |
| 3 | G.UI | 의 | の | Often dropped in speech (엄마 친구), unlike の. | — |
| 4 | G.ADN_ADJ | -(으)ㄴ + 명사 (형용사) | 形容詞連体形 | Adjectives need a modifier ending; no bare 終止形 before a noun. | — |
| 4 | G.DO | 도 | も | Close match. | — |
| 5 | G.PAST | -았/었- | た | Also used for resulting states where Japanese uses ている (결혼했어요 = 結婚している). | — |
| 5 | G.PLAIN_PRES | -ㄴ/는다 | 書き言葉の現在形 (である体) | Written/plain style; in speech it sounds like narration or exclamation. | — |
| 5 | G.FUT | -(으)ㄹ 것이다 / 거예요 | つもりだ／だろう | Covers both intention and conjecture; Japanese splits them. | — |
| 6 | G.HAEYO | -아/어요 | です・ます | Everyday polite; less formal than です・ます feels in writing. | — |
| 6 | G.HAMNIDA | -(스)ㅂ니다 | です・ます (改まった) | Formal/news/announcement register; no exact Japanese level. | — |
| 6 | G.BANMAL | -아/어 (반말) | タメ口 | Same form serves statement, question, command, suggestion by intonation. | — |
| 6 | G.HUMBLE_PRON | 저/제 vs 나/내 | 私 vs 僕・俺 | Choice is tied to the speech level, not gender. | — |
| 7 | G.IRREG_B | ㅂ 불규칙 | — | — | — |
| 7 | G.IRREG_D_S | ㄷ / ㅅ 불규칙 | — | — | — |
| 7 | G.IRREG_REU_L | 르 불규칙 / ㄹ 탈락 | — | — | — |
| 8 | G.ADV_GE | -게 (부사형) | 〜く／〜に | Also 'so that' (Stage 8 point), unlike 〜く. | — |
| 8 | G.NEG_AN | 안 + 용언 | 〜ない | Pre-verbal; Japanese negates with a suffix. | — |
| 8 | G.JI_ANTA | -지 않다 | 〜ない (長形) | Long negation; more neutral/written than 안. | — |
| 9 | G.ANIDA | 아니다 | ではない | Takes 이/가 on the noun (학생이 아니에요). | — |
| 10 | G.COUNTERS | 고유어/한자어 숫자 + 단위 | 数詞＋助数詞 | Native numbers for hours/items/age, Sino for minutes/dates/money. | — |
| 11 | G.DONGAN | 동안 | 間 | Close match. | — |
| 12 | G.MAN | 만 | だけ／ばかり | Close match. | — |
| 12 | G.ESEO | 에서 | で／から | 에서 = place of action (で) and origin (から); 에 = location of existence (に). | — |
| 12 | G.BUTEO_KKAJI | 부터/까지 | から／まで | 부터 is time/order; spatial 'from' is 에서. | — |
| 12 | G.EURO | (으)로 | で／へ／に | Means, direction, and change-into (으로 바뀌다). | — |
| 13 | G.WA_GWA | 와/과, 하고, (이)랑 | と | Three registers: 와/과 written, 하고 neutral, 랑 casual. | — |
| 13 | G.EGE | -에게 | に | Only for people/animals (places take 에). | — |
| 13 | G.HANTE | -한테 | に | Spoken form of 에게. | — |
| 13 | G.KKE | -께 | に (尊敬) | Honorific 에게; no particle-level honorific in Japanese. | — |
| 13 | G.WIHAE | 위해(서) | ために | Close match (N을 위해, -기 위해). | — |
| 13 | G.E_DAEHAE | 에 대해(서) | について | Close match. | — |
| 14 | G.PASSIVE | -이/히/리/기- (피동) | れる／られる | Lexical, not productive; many verbs use -아/어지다 or 되다 instead. | — |
| 15 | G.A_HADA | -아/어하다 | 〜がる | Turns a feeling adjective into a verb (좋아하다, 싫어하다). | — |
| 16 | G.JEOK | -적 / -적으로 / -적이다 | 的 | Same Sino suffix; 적 takes 인 before nouns (일반적인). | — |
| 16 | G.SEUREOPDA | -스럽다 | 〜らしい | Not conjecture (らしい 推量); only 'seeming/full of'. | — |
| 17 | G.GO | -고 | 〜て (並列) | Listing/sequence; cause-sequence uses -아/어서, not -고. | — |
| 17 | G.GO_SIPDA | -고 싶다 | 〜たい | Third person uses -고 싶어하다 (〜たがる). | — |
| 18 | G.GO_ITDA | -고 있다 | 〜ている (進行) | Progressive only; resultant ている is -아/어 있다 or past. | — |
| 18 | G.EOJIDA | -아/어지다 | 〜くなる | With adjectives = become; with verbs = passive (Lesson 14 territory). | — |
| 19 | G.BODA | 보다 / 더 / 가장 | より／もっと／一番 | Close match. | — |
| 20 | G.NEG_MOT | 못 + 용언 | 〜できない | Inability by negation, not a potential form. | — |
| 20 | G.JI_MOTHADA | -지 못하다 | 〜できない (長形) | Long form of 못. | — |
| 21 | G.QWORDS | 왜/언제/어디/누구/어떻게/뭐/어느/몇 | 疑問詞 | Same words double as indefinites (뭐 = 何か) by intonation. | — |
| 23 | G.IRREG_H | ㅎ 불규칙 (이렇다, 빨개요) | — | — | — |
| 24 | G.GI_JEONE | -기 전에 | 〜前に | Close match. | — |
| 24 | G.EUN_HUE | -(으)ㄴ 후에 | 〜た後で | Close match; also -(으)ㄴ 다음에. | — |
| 25 | G.AMU | 아무도/아무나, 누구나/누군가 | 誰も／誰でも／誰か | 아무도 needs a negative predicate, like 誰も. | — |
| 26 | G.ADN_VERB | -는 / -(으)ㄴ / -(으)ㄹ + 명사 | 動詞連体形 | Tense lives in the modifier ending (먹는/먹은/먹을). | — |
| 26 | G.NEUN_GEOT | -는 것 | 〜こと／〜の | Covers both こと and の. | — |
| 27 | G.DEON | -던 / -았던 | 〜ていた (回想) | Retrospective; no single Japanese form. | — |
| 28 | G.ADN_ITDA | 있다/없다 + -는 (맛있는) | — | 있다/없다 adjectives take -는, not -(으)ㄴ. | — |

## Example row format
| Lesson | Code | KO | JA | Differs | Kiwi pattern |
|---|---|---|---|---|---|
| (n) | G.KIRO_HADA | -기로 하다 | 〜ことにする | (note) | `ETN(기) + JKB(로) + VV(하)` |

## Priority threads beyond HTSK order (from prior study)
- -는데 (vs. -지만) as the conversational けど
- Honorific system: -(으)시-, humble verbs, honorific nouns
- -더니 retrospective connective
- Polysemous verb schemas (들어가다, 맞다, 생기다, 챙기다)
