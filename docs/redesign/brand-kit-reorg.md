# Brand Kit reorganisation: context pages for marketers

Status: built (2026-10-06). Builds on `brand-kit-template.md`.

## Feedback

- Reorganise and look cleaner.
- Today it reads like data analytics: tables of figures with no "so what". A marketer needs context
  pages: what is going on, what it means for campaigns, then the evidence behind it.
- Channels are missing, and marketers think in channels.
- Nothing is cut or truncated; the content is reorganised.

## Tabs (left pane, under Brand Kit)

| Tab | The question it answers | Content (each fact appears once) |
|---|---|---|
| **Brand IQ** (overview, the brand on a page) | What do I need to know before planning anything? | One-page brief: problem, objective, audience, message, channels, proof, watch-outs. Identity, unmet need, key objectives, current plan (strategic imperatives, growth). Source legend and the AI-draft banner, shown only here. How complete the kit is, per tab |
| **Market** | Where are we winning and losing, and where is the headroom? | Brand situation; where patients drop off (patient flow); where to focus (US geography); competition grid; market access; forecast, KPIs; client data; what has worked |
| **Audiences** | Who are we talking to and what moves them? | Segments on the adoption ladder, HCP personas, patients and their journey, who shapes opinion (KOLs), where the treaters are, patient education |
| **Message & Voice** | What do we say, and how? | Positioning, Big Idea, core claim, message matrix, voice and tone, words to use and avoid (one list) |
| **Channels** (new) | Where and when do we reach them? | See below |
| **Product & Proof** | What can we claim, and what backs it? | Product profile, indications, label and safety, clinical evidence, references (one table) |
| **Compliance** | What must every campaign respect? | SOPs, approval workflow, pre-launch checklist, eligibility, channel rules (also linked from Channels), do and don't, regulatory baseline |

## Context-page pattern (every tab)

1. **The brief**: up to 3 short bullets in marketing language ("Treaters know Cablivi but default to plasma
   exchange alone; the opening is the ER, where the first decision is made").
2. **What it means for campaigns**: 3–5 implications, written as do this / watch out, each citing
   the section it comes from.
3. **Behind this**: the existing tables and figures, below, unchanged in content.
4. **Still needed**: one box listing what's missing, with a link to the Brand IQ Agent, instead of
   "Needs input" scattered through the page.

Headings become marketer questions: "Patient flow" becomes "Where patients drop off", "US geography"
becomes "Where to focus", and "Key opinion leaders" becomes "Who shapes opinion".

The brief and implications are written by the model from the kit (a `context` skill in
`kit_proposer`, one per tab, stored in `kit.context[tab]`). They carry the same source badge: brand
plan > public data > AI draft. The brand plan wins on conflicts. With no model, the tab shows its
evidence and says "Brief not written yet".

## Length and readability

Everything should be readable at a glance and written in bullets:

| Item | Rule |
|---|---|
| Brief | At most 3 bullets of 15 words or fewer. Each bullet starts with a bold phrase of 2–4 words |
| What it means | 3–5 bullets, each starting **Do** or **Watch**, 20 words or fewer, with one source chip |
| Long text (label sections, value story, persona behaviours, SOP rules) | Shown as 3–5 key-point bullets. The original stays one click away ("Full text"), so nothing is lost |
| Table cells | 20 words or fewer. Anything longer becomes bullets inside the cell |
| Numbers | The figure comes first and in bold: **64% → 85%** ER/ICU awareness by Q4'26 |
| Persona cards | At most 3 bullets per part (behaviour, barrier, message) |
| Language | Plain words, no unexplained abbreviations, at most one idea per bullet |

The limits are written into the model prompts (`context`, `channels`, and a `digest` skill that turns
long fields into bullets). The bullets are stored next to the original (`field_bullets`), and the
original is never overwritten. A digest of brand-plan text keeps the brand-plan badge.

## Channels tab

| Section | Content | Source |
|---|---|---|
| Channel brief | Which channels carry the strategy and why | Model, from the sections below |
| Channel mix by audience | A matrix of audience × channel, with each cell showing the role (awareness / education / conversion / retention) and the reach % | Brand plan activities; client data reach (marked synthetic) |
| Channel cards | Per channel: its role, the content formats that work, cadence, the KPI to watch, what has worked (proof points), and its compliance rule | Activities, proof points, compliance channel rules |
| Journey × channel | Patient and HCP journey stages × channels: where each stage is reached | Care continuum, patient flow, activities |
| Moments | Congresses, awareness days, data read-outs, launches | Plan calendar; AI draft for gaps |

There is a new `channels` skill in `kit_proposer` that fills gaps from the plan and public data and
marks them as AI drafts. Brand-plan activities are never overwritten.

## Look

- One block style: the title line carries the title, the source badge, and at most one action.
- Source and date go in a small block footer, not under every row.
- At the top of each tab, a section index of chips that jump to each section.
- Short blocks sit two to a row; long tables are full width. Records are shown as tables and people
  as cards.

## Build

- Frontend:
  - split `BrandKitPage.tsx` into one file per tab;
  - add the routes `iq/kits` (Brand IQ), `iq/market`, `iq/personas` (Audiences), `iq/message`,
    `iq/channels`, `iq/product` and `iq/guardrails`;
  - update the left pane;
  - write the shared Block, footer, StillNeeded, SectionIndex and ContextBrief components.
- Backend:
  - add the `context` and `channels` skills to `kit_proposer.SKILLS` and to the Brand IQ Agent's
    steps (strategy step);
  - add `POST /api/brand-kits/{brand}/context/{tab}` to rewrite one brief on demand.
- The Brand IQ Agent canvas shows the Brand IQ overview, with the tabs available inside it.
