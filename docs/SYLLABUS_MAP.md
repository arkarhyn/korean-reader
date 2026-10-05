# SYLLABUS_MAP

Map only. Do NOT copy HowToStudyKorean text. Columns:
HTSK lesson | grammar code | label (KO) | Japanese parallel | where it differs | Kiwi pattern

Source of truth: `content/seed/grammar_points.json` (these tables are rendered from it;
re-render after editing). Lesson cards: `content/grammar/lessons/<code>.json` (✎ = has one).

Current position: around Lesson 29 (-기 / -(으)ㅁ nominalization).
Lessons 1-28 are verified by the Stage 4 grammar check, not assumed. Lessons 29+ have no
state row until their lesson card is finished (Stage 8, DECISIONS 92-97).

- L1-28: drafted by Claude, approved by Austin 2026-10-03; each has 2 placement check
  sentences (`content/placement/grammar.json`). Left out: 이래로/이내 (L24), 들 (L12),
  compound verbs (L15); 에게서/한테서 are seeded.
- L29-50 + priority threads: drafted in Stage 8 (2026-10-05) from the HTSK lesson index
  (titles only). **Pending Austin's review.** Skipped: L34 (vocabulary lesson).
- Teaching order = `teach_order` if set, else the HTSK lesson. Priority threads (from prior
  study) are pulled forward: -는데 after -아/어서, -(으)니까 after -기 때문에, -더니 and
  -기로 하다 after L50. Their Lesson column shows HTSK's own lesson (-더니: not in HTSK 1-91).

Pattern notation: `TAG(forms)` per Kiwi morpheme, `+` = next morpheme, `;` = alternative,
`~re` = regex on the form, `irr` = Kiwi tagged the stem irregular (VV-I/VA-I), `final ㅂ` =
final consonant of the stem, `*` = any tag. Matching code: `server/app/analyzer/patterns.py`.
The draft checker ignores a match lying wholly inside a usable point's match (-기 in -기 전에).

## Lessons 1-28

| Lesson | Code | KO | JA | Differs | Kiwi pattern |
|---|---|---|---|---|---|
| 1 | G.TOPIC | 은/는 | は | Close match, incl. contrast use. | `JX(은/는/ᆫ)` |
| 1 | G.COPULA | 이다 | だ／である | Attaches to the noun and conjugates like a verb (학생이에요). | `VCP` |
| 2 | G.SUBJ | 이/가 | が | Close match; 이/가 also marks the complement of 되다/아니다. | `JKS(이/가)` |
| 2 | G.ISSTA | 있다/없다 | ある・いる／ない | No animate/inanimate split; also 'to have'. | `VA\|VV(있/없/계시)` |
| 3 | G.OBJ | 을/를 | を | Used with 좋아하다 where Japanese uses が (好きだ). | `JKO` |
| 3 | G.UI | 의 | の | Often dropped in speech (엄마 친구), unlike の. | `JKG(의)` |
| 4 | G.ADN_ADJ | -(으)ㄴ + 명사 (형용사) | 形容詞連体形 | Adjectives need a modifier ending; no bare 終止形 before a noun. | `VA\|XSA + ETM(ᆫ/은)` |
| 4 | G.DO | 도 | も | Close match. | `JX(도)` |
| 5 | G.PAST | -았/었- | た | Also used for resulting states where Japanese uses ている (결혼했어요 = 結婚している). | `EP(었/았/였/ᆻ)` |
| 5 | G.PLAIN_PRES | -ㄴ/는다 | 書き言葉の現在形 (である体) | Written/plain style; in speech it sounds like narration or exclamation. | `EF(는다/ᆫ다)` |
| 5 | G.FUT | -(으)ㄹ 것이다 / 거예요 | つもりだ／だろう | Covers both intention and conjecture; Japanese splits them. | `ETM(ᆯ/을) + NNB(거/것) + VCP` |
| 6 | G.HAEYO | -아/어요 | です・ます | Everyday polite; less formal than です・ます feels in writing. | `EF(~요$) ; JX(요)` |
| 6 | G.HAMNIDA | -(스)ㅂ니다 | です・ます (改まった) | Formal/news/announcement register; no exact Japanese level. | `EF(~^(ᆸ\|습)(니다\|니까\|시오)$)` |
| 6 | G.BANMAL | -아/어 (반말) | タメ口 | Same form serves statement, question, command, suggestion by intonation. | `EF(어/아/여/야/…)` |
| 6 | G.HUMBLE_PRON | 저/제 vs 나/내 | 私 vs 僕・俺 | Choice is tied to the speech level, not gender. | `NP(저/저희/나) ; MM(내)` |
| 7 | G.IRREG_B | ㅂ 불규칙 | — | — | `VV\|VA(irr, final ㅂ) + *(~^[어아으와워었았])` |
| 7 | G.IRREG_D_S | ㄷ / ㅅ 불규칙 | — | — | `VV\|VA(irr, final ㄷ/ㅅ) + *(~^[어아으었았])` |
| 7 | G.IRREG_REU_L | 르 불규칙 / ㄹ 탈락 | — | — | `VV\|VA(~르$) + *(~^[어아]) ; VV\|VA(final ㄹ) + *(~^(니\|ᆫ\|ᆸ\|ᆯ\|세\|시\|오))` |
| 8 | G.ADV_GE | -게 (부사형) | 〜く／〜に | Also 'so that' (Stage 8 point), unlike 〜く. | `VA\|XSA + EC(게)` |
| 8 | G.NEG_AN | 안 + 용언 | 〜ない | Pre-verbal; Japanese negates with a suffix. | `MAG(안)` |
| 8 | G.JI_ANTA | -지 않다 | 〜ない (長形) | Long negation; more neutral/written than 안. | `EC(지) + VX(않)` |
| 9 | G.ANIDA | 아니다 | ではない | Takes 이/가 on the noun (학생이 아니에요). | `VCN` |
| 10 | G.COUNTERS | 고유어/한자어 숫자 + 단위 | 数詞＋助数詞 | Native numbers for hours/items/age, Sino for minutes/dates/money. | `NR + NNB\|NNG ; MM(한/두/세/네/…) + NNB\|NNG` |
| 11 | G.DONGAN ✎ | 동안 | 間 | Close match. | `NNG(동안)` |
| 12 | G.MAN | 만 | だけ／ばかり | Close match. | `JX(만)` |
| 12 | G.ESEO | 에서 | で／から | 에서 = place of action (で) and origin (から); 에 = location of existence (に). | `JKB(에서)` |
| 12 | G.BUTEO_KKAJI | 부터/까지 | から／まで | 부터 is time/order; spatial 'from' is 에서. | `JX(부터/까지)` |
| 12 | G.EURO | (으)로 | で／へ／に | Means, direction, and change-into (으로 바뀌다). | `JKB(로/으로)` |
| 13 | G.WA_GWA | 와/과, 하고, (이)랑 | と | Three registers: 와/과 written, 하고 neutral, 랑 casual. | `JC\|JKB(와/과/하고/랑/…)` |
| 13 | G.EGE | -에게 | に | Only for people/animals (places take 에). | `JKB(에게)` |
| 13 | G.HANTE | -한테 | に | Spoken form of 에게. | `JKB(한테)` |
| 13 | G.KKE | -께 | に (尊敬) | Honorific 에게; no particle-level honorific in Japanese. | `JKB(께)` |
| 13 | G.WIHAE ✎ | 위해(서) | ために | Close match (N을 위해, -기 위해). | `VV(위하)` |
| 13 | G.E_DAEHAE ✎ | 에 대해(서) | について | Close match. | `JKB(에) + VV(대하)` |
| 14 | G.PASSIVE | -이/히/리/기- (피동) | れる／られる | Lexical, not productive; many verbs use -아/어지다 or 되다 instead. | `VV(열리/닫히/들리/잡히/…)` |
| 15 | G.A_HADA | -아/어하다 | 〜がる | Turns a feeling adjective into a verb (좋아하다, 싫어하다). | `EC(어/아) + VX(하)` |
| 16 | G.JEOK | -적 / -적으로 / -적이다 | 的 | Same Sino suffix; 적 takes 인 before nouns (일반적인). | `XSN(적)` |
| 16 | G.SEUREOPDA ✎ | -스럽다 | 〜らしい | Not conjecture (らしい 推量); only 'seeming/full of'. | `XSA(스럽)` |
| 17 | G.GO | -고 | 〜て (並列) | Listing/sequence; cause-sequence uses -아/어서, not -고. | `EC(고)` |
| 17 | G.GO_SIPDA | -고 싶다 | 〜たい | Third person uses -고 싶어하다 (〜たがる). | `EC(고) + VX(싶)` |
| 18 | G.GO_ITDA | -고 있다 | 〜ている (進行) | Progressive only; resultant ている is -아/어 있다 or past. | `EC(고) + VX(있/계시)` |
| 18 | G.EOJIDA ✎ | -아/어지다 | 〜くなる | With adjectives = become; with verbs = passive (Lesson 14 territory). | `EC(어/아) + VX(지)` |
| 19 | G.BODA | 보다 / 더 / 가장 | より／もっと／一番 | Close match. | `JKB(보다) ; MAG(더/가장/제일)` |
| 20 | G.NEG_MOT | 못 + 용언 | 〜できない | Inability by negation, not a potential form. | `MAG(못)` |
| 20 | G.JI_MOTHADA | -지 못하다 | 〜できない (長形) | Long form of 못. | `EC(지) + MAG(못) + *(하) ; EC(지) + VX(못하)` |
| 21 | G.QWORDS | 왜/언제/어디/누구/어떻게/뭐/어느/몇 | 疑問詞 | Same words double as indefinites (뭐 = 何か) by intonation. | `MAG\|NP\|MM\|IC(왜/언제/어디/누구/…) ; VA(어떻)` |
| 23 | G.IRREG_H ✎ | ㅎ 불규칙 (이렇다, 빨개요) | — | — | `VA(irr, final ㅎ) + *(~^[어아었았ᆫᆯᆷ으])` |
| 24 | G.GI_JEONE | -기 전에 | 〜前に | Close match. | `ETN(기) + NNG(전)` |
| 24 | G.EUN_HUE | -(으)ㄴ 후에 | 〜た後で | Close match; also -(으)ㄴ 다음에. | `ETM(ᆫ/은) + NNG(후/다음/뒤)` |
| 25 | G.AMU | 아무도/아무나, 누구나/누군가 | 誰も／誰でも／誰か | 아무도 needs a negative predicate, like 誰も. | `NP(아무) + JX(도/나) ; NP(누구) + JX(나/든지/ᆫ가/도) ; NP(아무것/누군가/아무데)` |
| 26 | G.ADN_VERB | -는 / -(으)ㄴ / -(으)ㄹ + 명사 | 動詞連体形 | Tense lives in the modifier ending (먹는/먹은/먹을). | `VV\|XSV + ETM(는/ᆫ/은/ᆯ/…)` |
| 26 | G.NEUN_GEOT | -는 것 | 〜こと／〜の | Covers both こと and の. | `ETM(는) + NNB(것/거)` |
| 27 | G.DEON | -던 / -았던 | 〜ていた (回想) | Retrospective; no single Japanese form. | `ETM(던)` |
| 28 | G.ADN_ITDA | 있다/없다 + -는 (맛있는) | — | 있다/없다 adjectives take -는, not -(으)ㄴ. | `VA(~(있\|없)$) + ETM(는)` |

## Lessons 29-50 + priority threads (Stage 8 draft)

| Lesson | Code | KO | JA | Differs | Kiwi pattern |
|---|---|---|---|---|---|
| 29 | G.GI_NOMINAL ✎ | -기 (명사형) | 〜こと／〜の (名詞化) | Fixed frames (-기 싫다/쉽다/좋다) where Japanese uses 〜のが嫌だ/〜やすい. | `ETN(기)` |
| 29 | G.EUM ✎ | -(으)ㅁ (명사형) | 〜こと (書き言葉) | Written/notice style (확인함) and fixed nouns (기쁨); in speech -는 것 is used instead. | `ETN(ᆷ/음) ; EF(ᆷ/음)` |
| 30 | G.NEUNJI | -는지 / -(으)ㄴ지 (whether) | 〜か (間接疑問) | Embedded question ending; 〜かどうか uses -는지 안 -는지. | `EC(는지/ᆫ지/은지/ᆯ지/…)` |
| 30 | G.EUN_JI | -(으)ㄴ 지 (since) | 〜てから (時間) | Only with a time span + 되다/지나다 (온 지 1년 됐다); not a general 'since'. | `ETM(ᆫ/은) + NNB(지)` |
| 31 | G.NEUN_GEOSIDA | -는 것이다 / -는 거예요 | 〜のだ／〜んです | Explanatory 'it's that...'; much less frequent than んです. | `ETM(는/ᆫ/은) + NNB(것/거) + VCP` |
| 31 | G.NEUNDANEUN | -ㄴ/는다는 것 (the fact that) | 〜ということ | Close match; contracted 다는 is the quoting ending + modifier. | `ETM(~다는$) + NNB(것/거)` |
| 32 | G.RYEOGO | -(으)려고 (하다) | 〜ようと(する) | Also 'in order to' with any following verb; -(으)러 only before motion verbs. | `EC(려고/으려고)` |
| 32 | G.REO | -(으)러 가다/오다 | 〜に行く／来る | Close match; only with motion verbs. | `EC(러/으러)` |
| 32 | G.A_BODA | -아/어 보다 (try) | 〜てみる | Close match; past -아/어 봤다 = 'have done (experience)' like 〜たことがある. | `EC(어/아) + VX(보)` |
| 33 | G.JUNG | 중 / -는 중 | 〜中／〜ている最中 | Close match (회의 중 = 会議中); -는 중 adds 'in the middle of'. | `NNB(중)` |
| 35 | G.EUL_GEOT_GATDA | -(으)ㄹ/는 것 같다 | 〜そうだ／〜ようだ／〜と思う | One form covers guess, impression and soft opinion; tense sits in the modifier. | `ETM(ᆯ/을/는/ᆫ/…) + NNB(것/거) + VA(같)` |
| 36 | G.A_BOIDA | -아/어 보이다 / N같이 보이다 | 〜く見える／〜そうに見える | Adjective + 보이다 only; for verbs use -는 것 같다. | `EC(어/아) + VV(보이) ; JKB(같이) + VV(보이)` |
| 37 | G.A_SEO | -아/어서 | 〜て／〜ので | Cause or sequence; cannot take past tense or a command/suggestion after a cause. | `EC(어서/아서/여서/라서/…)` |
| 76 (taught at 37.5) | G.NEUNDE | -는데 / -(으)ㄴ데 | 〜けど／〜んだけど (前置き) | Sets background more than it contrasts; ending a sentence with -는데(요) softens it. | `EC\|EF(~^(는\|ᆫ\|은)데(요)?$)` |
| 38 | G.TTAEMUNE | -기 때문에 / N 때문에 | 〜ので／〜のせいで | More explicit/written than -아/어서; N 때문에 often negative (のせい). | `NNB(때문)` |
| 81 (taught at 38.5) | G.NIKKA | -(으)니까 | 〜から | Subjective reason; fine before commands/suggestions, unlike -아/어서. | `EC(니까/으니까/니/으니)` |
| 39 | G.SI_HON | -(으)시- (주체 높임) | お〜になる／尊敬語 | Productive suffix on any predicate; used for parents/elders even in family talk. | `EP(시/으시) ; EF(~^(으)?(세요\|십시오\|셔요\|셔)$) ; VV(주무시/드시/계시/잡수시/…)` |
| 39 | G.HON_WORDS | 높임 어휘 (드리다, 계시다, 께서, 댁, 진지...) | 尊敬語／謙譲語の語彙 | Like 召し上がる/伺う: suppletive words, plus 께서 as honorific subject marker. | `JKS(께서) ; VV(드리/뵙/뵈/여쭈/…) ; NNG(진지/댁/연세/성함/…)` |
| 40 | G.SEYO | -(으)세요 (polite request) | 〜てください | Same ending as an honorific statement/question; context decides. | `EF(세요/으세요)` |
| 40 | G.A_RA | -아/어라 (command) | 〜ろ／〜なさい | Blunt plain command; parents to children, or quoted/written. | `EF(어라/아라/여라)` |
| 41 | G.A_JUDA | -아/어 주다 / 드리다 | 〜てくれる／〜てあげる | No くれる/あげる split: direction comes from context; 드리다 for elders. | `EC(어/아) + VX(주/드리)` |
| 42 | G.EUL_TTAE | -(으)ㄹ 때 | 〜とき | Always the -(으)ㄹ form, even for past (갔을 때 = 行ったとき). | `ETM(ᆯ/을) + NNG(때)` |
| 43 | G.MYEON | -(으)면 | 〜たら／〜ば／〜と | One ending for たら/ば/と. | `EC(면/으면)` |
| 43 | G.NDAMYEON | -ㄴ/는다면 | 〜としたら／もし〜なら | Hypothetical/unlikely; -(으)면 is the everyday conditional. | `EC(~다면$)` |
| 44 | G.JA | -자 (let's, 반말) | 〜よう (意向形) | Plain 'let's' only among close equals. | `EF(자)` |
| 44 | G.EUPSIDA | -(으)ㅂ시다 | 〜ましょう | Not for elders (sounds like an order); use -(으)시죠 or -아/어요. | `EF(ᆸ시다/읍시다)` |
| 44 | G.EULLAE | -(으)ㄹ래(요) | 〜する？／〜しようか | Asks the listener's wish; also 'I want to' in statements. | `EF(~^(ᆯ\|을)래(요)?$)` |
| 45 | G.EUL_SU_ITDA | -(으)ㄹ 수 있다/없다 | 〜ことができる | Also 'might/possible' (그럴 수 있다); potential verbs don't exist. | `ETM(ᆯ/을) + NNB(수) + *(있/없) ; ETM(ᆯ/을) + NNB(수) + JX + *(있/없) ; ETM(ᆯ/을) + NNB(수) + JKS + *(있/없)` |
| 46 | G.A_YA_HADA | -아/어야 하다/되다 | 〜なければならない | Positive frame ('only if ~ does it work'), shorter than Japanese. | `EC(어야/아야/여야) + VX\|VV(하/되)` |
| 46 | G.EUL_PILYO | -(으)ㄹ 필요가 있다/없다 | 〜必要がある | Close match. | `ETM(ᆯ/을) + NNG(필요)` |
| 47 | G.JIMAN | -지만 | 〜けど／〜が | Contrast only; the softer background けど is -는데 (thread). | `EC\|EF(지만)` |
| 48 | G.A_DO | -아/어도 (even if) | 〜ても | Close match; 아무리 -아/어도 = いくら〜ても. | `EC(어도/아도/여도/라도/…)` |
| 49 | G.A_DO_DOEDA | -아/어도 되다 | 〜てもいい | Close match; 안 -아/어도 되다 = 〜なくてもいい. | `EC(어도/아도/여도) + VV\|VA(되/괜찮)` |
| 50 | G.EUL_YEJEONG | -(으)ㄹ 예정/계획이다 | 〜予定だ／〜つもりだ | Close match. | `ETM(ᆯ/을) + NNG(예정/계획)` |
| — (taught at 50.5) | G.DEONI | -더니 | 〜たら (発見)／〜と思ったら | Speaker's past observation leading to a change or result; no single Japanese form. | `EC(더니/었더니/았더니)` |
| 87 (taught at 50.7) | G.KIRO_HADA | -기로 하다 | 〜ことにする | Close match; 했다 for a decision already made. | `ETN(기) + JKB(로) + VV(하)` |
