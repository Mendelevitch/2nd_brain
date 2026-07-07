# Translation Prompt (Two-Pass Ingest)

Process everything in `/raw` into atomic wiki entries in `/wiki`. This happens in two passes — do not skip Pass 1 even if the raw queue looks simple.

**Before Pass 1, also pull new meetings from Granola** (see "Granola" under Source types) — this is the primary meeting-notes source. **As a fallback, also scan the Notion TLDV page** (see "Notion TLDV (fallback)" under Source types) for anything still landing there. Treat both intakes exactly like raw files. The rest of the process — analysis, atomization, wiki merge — is identical; only the intake and the "after processing" step differ per source.

---

## Pass 1 — Analysis

Read all files in `/raw`. For each file, produce a structured analysis block:

```
FILE: <filename>
SOURCE TYPE: <thought|conversation|external_link|transcript|pdf|document|ad_campaign>
CONCEPTS: <comma-separated list of distinct concepts, entities, topics>
AFFECTS WIKI: <list of existing wiki files likely to be updated, or NEW for new entries>
OVERLAPS WITH: <other files in this batch that touch the same concepts — merge these in Pass 2>
UNCERTAINTIES: <anything ambiguous, unclear, or that requires a judgment call>
```

After producing all analysis blocks, review them as a whole:
- Are multiple raw files about the same concept? Plan one combined wiki update, not separate ones.
- Which wiki files need to be read before writing? Load them now, before Pass 2.

Only proceed to Pass 2 after you have read all affected wiki files.

---

## Pass 2 — Generation

Execute the wiki updates based on your analysis. Apply all translation rules below.

---

## Source types

Each raw file should declare its source. Handle them differently:

**`source: thought`** (or no source field)
the owner's own thinking — ideas, observations, opinions, decisions. Treat as primary material. Extract and atomize freely. Preserve voice. These are the most valuable pieces of information shared with you - treat them with care and respect. 

**`source: conversation`** or **`source: granola`**
A dialogue, call transcript, or back-and-forth with another person or AI. the owner's contributions are primary material. Other participants' ideas are secondary — include them if on topic, but attribute them clearly.

If the file contains a `Meeting ID:` field (Granola export), construct the source URL as `https://notes.granola.ai/d/<meeting-id>` and include it in every wiki entry this file feeds, alongside the archive link. Format: `→ [Meeting recording](https://notes.granola.ai/d/<meeting-id>)`.

**Extract competitive and market intelligence from other speakers, not just the owner's positions.** If the other person describes how their business works, their pricing, their workflow, their client model, their tools — this is primary intelligence. Log it verbatim in the relevant wiki entry. The failure mode is focusing on the outcome of the conversation (partnership agreed, client referred) while skipping how the other person actually operates. That operational detail is often the most valuable thing in the call.

**Do not limit extraction to decisions and conclusions.** Rich conversations contain far more wiki-worthy material than their outcomes. Extract everything a person would remember as valuable if they'd been in the room:

- **Ideas** — product concepts, business ideas, naming, creative mechanics, even half-formed sparks. Especially half-formed — those get lost first.
- **Frameworks and mental models** — any structured way of thinking about a problem. If someone explains *why* something works, that's a framework worth preserving.
- **Arguments and reasoning chains** — not just conclusions, but the logic behind them. "X because Y because Z" — preserve the chain, not just X.
- **Concrete intelligence** — names, contacts, prices, market data, competitive intel, offers made. Log it verbatim.
- **Commitments and next steps** — what was decided, proposed, or offered. If someone said "I'll introduce you" or "call me next week", log it.
- **Quotes** — phrases that carry signal: precise, memorable, or revealing. Preserve in the speaker's own words, with attribution.
- **Personal reflections** — identity, values, self-assessments, lessons drawn. the owner saying something about himself at 40 is as wiki-worthy as a business framework.
- **Tensions and open questions** — things raised but not resolved. Active uncertainties are valuable to track.
- **Emotional signals** — what provoked excitement, doubt, frustration. These contextualize everything else.

If a conversation lasted 1+ hours and you produced fewer than 5–6 distinct wiki updates, you almost certainly missed something. Go back.

A digression that seems off-topic can be the most valuable thing in the transcript. Do not filter by "relevance to the main subject" — process the whole conversation.

**`source: group_chat`**
A transcript of a Telegram group chat episode (bounded by a 4-hour silence gap). The `chat:` field names the group. Multiple projects may be discussed in a single episode.

Process as follows:
1. Read the full transcript and identify distinct topic threads — a single episode often contains several unrelated conversations.
2. For each thread, determine if it relates to a project in `/projects/`. Check by folder name and by context (a chat named "unmute" will discuss unmute work, but also inlab, flo, etc.).
3. For each project touched: append a dated section to `/projects/{name}/chat-log.md` with extracted todos, decisions, and ideas. Format: `## YYYY-MM-DD — {chat title}`, then bullet points with author attribution.
4. For threads not linked to any specific project: extract ideas/decisions to wiki as usual (`source: conversation` rules apply).
5. Do NOT create a single monolithic entry — split by topic/project thread.
6. Todos directed at specific people (not the owner) → note them in the project log but don't add to Notion.

**`source: external_link`**
A URL pointing to an article, video, podcast, or other external content. Attempt to fetch and read the content. If accessible: extract only what's relevant to the owner's existing wiki topics or open questions — don't summarize the whole thing. If inaccessible (paywalled, restricted, dead): create a stub entry noting the URL and why it was flagged, and log it as unprocessed. Do not fabricate content about what the link might contain. Think, why would the owner save this link, connect to the topics of thinking and ideation. 

**`source: transcript`**
A transcript of external content (podcast, talk, interview) not primarily featuring the owner. Treat like a book or article — extract ideas that connect to existing wiki topics or open questions. Attribute clearly ("per X in [source]"). Don't present external views as the owner's.

**Granola (source `granola`)**
Granola is the primary meeting-notes tool going forward (replaces tl;dv for new calls). Meetings are fetched directly via the Granola MCP — no Notion inbox involved.

Sync state lives in `.granola-sync.json` at the repo root: `{"last_synced_at": "<ISO 8601 timestamp>"}`. If the file doesn't exist yet, this is the first run — process every meeting Granola returns, but stay conservative about the starting point (see step 4).

Process as follows:
1. Call `list_meetings` (Granola MCP) with `time_range: "custom"`, `custom_start: <last_synced_at>`, `custom_end: <now>` — this filters server-side by date. Returns `id`, `title`, `date`, and known participants per meeting.
2. Every meeting returned is a candidate (the date filter already excludes anything before `last_synced_at`).
3. For each meeting, call `get_meeting_transcript` with its `id` to pull the full transcript. Use `get_meetings` instead if you need the structured notes/summary rather than raw transcript. (`query_granola_meetings` is also available for ad-hoc natural-language lookups, but the ingest flow should use `list_meetings` + `get_meeting_transcript` for completeness.)
4. If a meeting has no transcript yet (still processing on Granola's side, or in progress), **skip it and do not let it advance the sync timestamp** — it'll be picked up on a later run once it's ready.
5. Route the content by what it actually is, using the source-type rules above — a call/meeting transcript is `source: conversation` (the owner's contributions are primary; attribute others). Apply all Pass 1 analysis and Pass 2 translation rules normally. If a transcript is too large to process in one pass, use the same swarm/chunking approach described under "Notion TLDV (fallback)" step 5 below.
6. **Save the transcript to `/archive`** like any processed raw file. Write it to `/archive/granola_<YYYYMMDD>_<kebab-title>.md` (date from the meeting; kebab-case the title). Start the file with a short header: the Granola meeting ID and the processed date. Then apply the normal **"Link the archived source"** rule.
7. Run **Pass 3 (People Profiles)** the same as for any call transcript.
8. **After all meetings in this run are handled**, write `.granola-sync.json` with the latest timestamp among the meetings you actually processed in step 3–6 (not "now," and not past anything skipped in step 4). This is the only state file for this source — don't create a second ledger.

**Notion TLDV (fallback, legacy — source `notion_tldv`)**
Kept for continuity now that Granola (above) is the primary meeting source. This only matters if something still lands on the old tl;dv Notion page — check it, but expect it to go quiet over time.

A Notion page where tl;dv auto-dumps call transcripts (and occasionally notes/links) as child pages. The page is the inbox; its child pages are the "files." Treat each new child page exactly like a raw file.

Page: **TLDV** — ID `3893fedb44a080bbaca4dc57246eac56` (https://www.notion.so/<your-workspace>/TLDV-<page-id>)

**Dedup via title marker.** A child page is considered processed once its title starts with `✅ `. That marker (set by us after processing) is the only record — there is no separate ledger.

Process as follows:
1. Fetch the TLDV page and list its child pages (Notion MCP — `notion-fetch`).
2. A child page is **new** if its title does **not** start with `✅ `. Skip the ones already marked.
3. For each new child page, fetch its full content (set `include_transcript: true` so transcripts come through, not a placeholder).
4. If the page is **blank** (tl;dv hasn't filled it yet), skip it and do NOT mark it — it'll be rechecked next run.
5. **If the fetch fails with a "content exceeds token limit" error** — the transcript is too large to process in one pass. Use the swarm approach:
   - The tool saves the oversized content to a temp file path — note that path.
   - Estimate the total character count (usually stated in the error). Divide into overlapping chunks of ~15,000 characters each (overlap 500 chars to avoid cutting mid-sentence).
   - Spawn parallel agents — one per chunk. Each agent receives: its character slice, the instruction to extract ALL wiki-worthy content without filtering (ideas, decisions, names, frameworks, commitments, tensions, quotes, business context — everything), and is told NOT to summarize or compress.
   - Merge all agent outputs before proceeding to Pass 2. Deduplicate across chunks.
   - **Do not use grep as a substitute.** Grep only finds what you already know to search for. A conversation can contain anything — unexpected names, unnamed startups, offhand decisions. Only full-text reading catches these.
6. Otherwise treat the content as a raw file and route it by what it actually is, using the source-type rules above: a meeting/call transcript → `source: conversation` (the owner's contributions are primary; attribute others); a saved link/URL → `source: external_link`; a plain note/idea → `thought` / `category: idea`. Apply all Pass 1 analysis and Pass 2 translation rules normally.
6. **Save the transcript to `/archive`** like any processed raw file. Write the child page's full content to `/archive/notion-tldv_<YYYYMMDD>_<kebab-title>.md` (date from the meeting/page title; kebab-case the title, URL-encode if needed). Start the file with a short header: the Notion page ID, the child-page URL, and the processed date. Then apply the normal **"Link the archived source"** rule — every wiki/project entry this transcript fed gets a `→ [filename](../archive/filename.md)` link at the bottom. (The `/archive` copy exists precisely because Notion pages can't be moved there.)
7. **Mark the page processed.** Once its `/archive` copy is written and the wiki updates are done, prepend `✅ ` to the child page's title (Notion MCP — `notion-update-page`, `update_properties` with the `title` property). Do not otherwise edit the page body, move it, delete it, or add comments — the title marker is the only change we make in Notion.

**`source: pdf`** / **`source: document`**
An external document, paper, or report. Same rules as `source: transcript`. Extract relevant ideas; attribute the source. 

**`category: event`**
A calendar event — meeting, birthday, appointment, deadline, or any time-bound thing. Always:
1. Create a Google Calendar event via the calendar MCP tool. Use all available details: title, date, time, location, attendees. If end time is not specified, default to 2 hours. Set a popup reminder 1 day before and 1 hour before.
Do not create a separate wiki entry and do not log to `reflections.md` — the calendar is the only record.

**`category: idea`** (or `source: self_text` with a short concept)
A naming idea, product spark, or short creative concept without an immediate project home. Route directly to `wiki/ideas.md`. Add under the appropriate section header (## Нейминг for names/wordplay, ## Идеи for concepts). Format: `**YYYY-MM-DD · Title**` followed by one or two sentences. Do not expand, explain, or build on the idea — preserve it as captured.

**Ad campaigns and creative case studies**
If the raw file body contains the word "кейс", "кампания",  — treat it as an ad campaign or creative case study regardless of other signals. Also catch it when content clearly describes a campaign or brand activation or SMM. Don't fold it into a topical wiki entry. Instead, create or update `/wiki/refs/ad-campaigns.md`. Each entry should include: brand, campaign name or description, year if known, original URL, the owner's comment verbatim (if present), and 2–3 sentences on what makes it notable — filtered through the owner's lens (craft, strategy, cultural tension, trust mechanics, originality). Group by brand or theme if the file grows large.

---

## Translation rules

- **Atomize concepts.** A note about "performance CMOs and brand strategy" should produce separate entries for `performance-marketing.md`, `brand-strategy.md`, `creative-agency.md` (or similar) — not one combined file. The raw note is the raw note; the wiki is the conceptual index.
- **One concept per file, kebab-case filename.** Name files after the concept, not the note.
- **Merge, never overwrite.** If the wiki entry already exists, read it first. Add only what is new, contradictory, or meaningfully extends what's already there. Don't repeat content already captured.
- **Preserve voice.** Keep the owner's original phrasing when it carries signal. Don't neutralize it into encyclopedia tone. This applies only to primary material (thoughts, conversations where the owner is speaking).
- **Attribute external ideas.** When content comes from an external source, note where it came from. Don't fold external claims into the wiki as if they were the owner's.
- **Link related entries** with relative markdown links at the bottom of each file.
- **Update `wiki/_index.md`** whenever a new wiki file is created. Add an entry in the appropriate section: `**filename.md** — 2–3 sentence description of what it contains.` If no section fits, add a new one. If the file already exists in the index, update its description if the content changed significantly.
- **Move processed files** from `/raw` to `/archive` with the same filename. Never delete.
- **Link the archived source.** After moving a raw file to `/archive`, add a direct link to it in every wiki entry that file fed. Put it at the bottom of the entry (or the relevant section) in the form `→ [filename](../archive/filename.ext)`, URL-encoding spaces and Cyrillic. If one entry was built from several raw files, link all of them; if several entries came from one file, each links back to it. This makes every entry traceable to its origin — see the "Archive Links" rule in `CLAUDE.md`. Source attribution in prose (date + type) is still required, but it does not replace the link.
- **Surface in projects.** If a raw note relates to a folder in `/projects`, append a concise update to that project's most relevant file (README or a dedicated notes file). For `source: group_chat` — always apply the group_chat rules above instead of this generic rule.
- **When uncertain, log it** inside the entry rather than guessing.

The goal: atomic, living articles that accumulate knowledge across many notes over time — not one file per note.

---

## Pass 3 — People Profiles

After Pass 2 wiki updates are done, update people profiles in `wiki/people/`.

**Every call transcript triggers a people pass.** For each identified participant (other than the owner):

1. **Read their existing profile** in `wiki/people/<name>.md`. If no profile exists, create one.
2. **Update these sections** with anything new from this call:
   - **Текущее состояние** — what's going on in their life/work right now
   - **Идейные треды** — new ideas or continuations of existing threads
   - **Психологические наблюдения** — tone shifts, what they actually came for, comfort level
   - **Хронология** — add this call's archive file as a source
3. **Log cross-call threads**: if an idea from a previous call appears again in a new form — note the evolution, not just the repetition. "Trust funnel discussed again — now applied to Flo case" > "discussed trust."
4. **Do NOT guess on identity.** If a name is ambiguous (e.g. "Настя", "Анастасия"), check `wiki/people-index.md` first. If still unclear after checking — stop and ask the owner before writing anything.
5. **Update `wiki/people-index.md`** if a new person is added.

**What to extract beyond facts:**
- What was this person's emotional state in this call? Opening tone vs. closing tone?
- What did they come for (stated) vs. what they seemed to actually need?
- What value did the owner deliver to them in this call?
- What patterns are they repeating across calls?

**Profile format** (use for new profiles):

```markdown
# [Full Name]

*[One-line description — role, relationship, location]*

---

## Кто он/она

## Мировоззрение и ценности

## Текущее состояние (YYYY-MM)

## Динамика отношений с Мишей

## Идейные треды

## Психологические наблюдения

## Хронология
```

---

## ⚠️ FINAL STEP — REQUIRED, NON-OPTIONAL

**After all wiki edits are complete, you MUST move every processed raw file from `/raw` to `/archive` using bash:**

```bash
mv /path/to/SimpleBrainMM/raw/FILENAME /path/to/SimpleBrainMM/archive/FILENAME
```

**Do not consider the task complete until:**
1. Every `.md` file you processed is gone from `/raw` (the `.gitkeep` file stays)
2. Each moved file appears in `/archive`
3. Every wiki entry that file fed has a `→ [filename](../archive/filename.md)` link at the bottom

This step is not optional. Wiki edits without archiving = task is unfinished. The user will know — `/raw` shows what was missed.
