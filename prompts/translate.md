# Translation Prompt (Two-Pass Ingest)

Process everything in `/raw` into atomic wiki entries in `/wiki`. This happens in two passes — do not skip Pass 1 even if the raw queue looks simple.

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
The owner's own thinking — ideas, observations, opinions, decisions. Treat as primary material. Extract and atomize freely. Preserve voice. These are the most valuable pieces of information shared with you - treat them with care and respect. 

**`source: conversation`**
A dialogue, call transcript, or back-and-forth with another person or AI. The owner's contributions are primary material. Other participants' ideas are secondary — include them, if they are on topic, but mention the author or source. Don't write up other people's positions as if they were the owner's. If the conversation produced a decision or conclusion, that's wiki-worthy; the discussion that got there usually isn't.

**`source: external_link`**
A URL pointing to an article, video, podcast, or other external content. Attempt to fetch and read the content. If accessible: extract only what's relevant to the owner's existing wiki topics or open questions — don't summarize the whole thing. If inaccessible (paywalled, restricted, dead): create a stub entry noting the URL and why it was flagged, and log it as unprocessed. Do not fabricate content about what the link might contain. Think, why would the owner save this link, connect to the topics of thinking and ideation. 

**`source: transcript`**
A transcript of external content (podcast, talk, interview) not primarily featuring the owner. Treat like a book or article — extract ideas that connect to existing wiki topics or open questions. Attribute clearly ("per X in [source]"). Don't present external views as the owner's.

**`source: pdf`** / **`source: document`**
An external document, paper, or report. Same rules as `source: transcript`. Extract relevant ideas; attribute the source. 

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
- **Surface in projects.** If a raw note relates to a folder in `/projects`, also update that project's notes.
- **When uncertain, log it** inside the entry rather than guessing.

The goal: atomic, living articles that accumulate knowledge across many notes over time — not one file per note.
