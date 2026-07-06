# Synthesis Prompt

Read all files in `/wiki`. Also scan filenames and dates in `/archive` for chronological signal.

Your job is not to summarize individual entries. Your job is to find what becomes visible only when you read everything at once.

---

## What to look for

**Recurring concepts**
Ideas that appear across multiple entries, possibly under different names or approached from different angles. The question is not just "this appears often" — it's "why does this keep returning, and what does the recurrence reveal?"

**Unexpected intersections**
Two entries that look unrelated but share underlying logic, structure, or tension. The insight is not the fact of connection — it's the specific nature of it. What does one entry illuminate about the other that neither entry makes explicit?

**Thinking evolution**
Where an idea in an older `/archive` file contradicts, complicates, or extends an idea in a current `/wiki` entry. Use dates to establish the direction. If a belief has shifted, name the shift and what likely caused it.

**Unresolved tensions**
Places where two positions in the wiki are genuinely in conflict. Don't resolve them. Don't synthesize them into a false unity. Name them precisely — the tension is often the most useful thing.

**Missing concepts**
Recurring themes or referenced ideas that don't yet have their own wiki entry. List them as gaps worth filling.

---

## Output

Two separate outputs per run:

### 1. `/wiki/synthesis.md`

Each synthesis run gets a dated section header (`## YYYY-MM-DD`).

For each insight:
- State what the pattern is (one sentence).
- State why it's interesting or non-obvious (one or two sentences).
- Name which wiki entries it connects.

Maximum 4–5 sentences per insight. No padding. No motivation. No editorializing.

If nothing genuinely new emerged since the last synthesis, say so in one line and stop.

### 2. Weekly digest in `/insights/YYYY-MM-DD-weekly-digest.md`

Always create a new file — never update an existing one. Use today's date for the filename. The digest is in Russian. Sections:

**### Сохранённые материалы недели**

For each raw file from the past 7 days with `source: external_link` or `source: transcript`:
- Title (or inferred topic if no title)
- Original URL
- 3–5 sentences in Russian summarising the key points — filtered through the owner's interests and wiki topics. Skip anything that isn't relevant to those domains.
- One sentence on why it's worth re-reading (or skip if it isn't).

If the source is an ad campaign or case study (see translate.md for definition), note it as **📌 Рекламный кейс** and link to the wiki reference entry that was created from it.

Order by date saved. If no external sources were saved this week, omit the section entirely.

---

## Source awareness

When synthesizing, track where ideas came from. The wiki should distinguish between:

- **The owner's own positions** — formed through his own thinking or conversation (`source: thought`, `source: conversation`)
- **External ideas he's engaging with** — drawn from links, transcripts, documents

A pattern that emerges entirely from external sources is not the same as a recurring theme in the owner's own thinking. Flag this distinction when it matters — e.g. "This idea appears repeatedly from external sources but the owner hasn't yet stated a position of their own."

Conversely: if an external source directly confirms, contradicts, or sharpens something already in the owner's thinking, that intersection is synthesis-worthy.

---

## What not to do

- Don't list what each wiki entry is about. That's just a table of contents.
- Don't find connections that are obvious from the filenames alone.
- Don't manufacture insight. If the wiki is too thin to synthesize, say so.
- Don't resolve tensions the wiki hasn't resolved. The unresolved state is the signal.
- Don't treat external ideas as the owner's positions. Attribution matters.
