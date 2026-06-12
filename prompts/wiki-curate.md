# Wiki Curation Prompt

Read all files in `/wiki`. Your job is to strengthen the wiki as a graph — find real conceptual connections and make them explicit inside the files. This is structural work, not content work: you are not adding new ideas, you are surfacing relationships that already exist.

---

## Pass 1 — Map the graph

For each wiki file, identify:
- Its **core concept** (one phrase)
- **Outgoing links** it already has
- **Candidate connections** — other wiki files it relates to, and the specific nature of the relationship

Produce a map like:

```
trust-framework.md — "working trust model"
  already links to: (none)
  should link to: brand-vulnerability.md (operationalises this framework), trust-neuroscience.md (biological basis), trust-theory-history.md (genealogy), paid-vs-organic-trust.md (applies framework to channel), trust-funnel-two-steps.md (applies to funnel)

brand-vulnerability.md — "vulnerability as trust mechanism"
  already links to: trust-framework.md, trust-theory-history.md
  should link to: brand-vulnerability-strategy.md (operational layer), trust-neuroscience.md (mechanism), paid-vs-organic-trust.md (channel implications)
```

Also flag:
- **Orphans** — files with no incoming links from any other file
- **Stubs** — files under ~150 words with no real content yet
- **Overlap candidates** — files that cover very similar ground and might warrant a merge note

---

## Pass 2 — Edit the files

Two types of links to add:

### 2a. Inline links — highest priority

When a file mentions a concept **by name in the body text** and that concept has its own wiki file, turn the first mention into a link. Examples:

- "Language bank" → `[Language bank](language-bank.md)`
- "trust framework" → `[trust framework](trust-framework.md)`
- "category design" → `[category design](category-design.md)`

Rules:
- Link only the **first** mention in the file, not every occurrence
- Match by concept name, not just filename — "vulnerability" links to `brand-vulnerability.md` if that's what's being discussed
- Don't link if the concept is only mentioned in passing with no real connection
- Don't change the prose — only wrap the existing words in a link

### 2b. See also section — for connections not mentioned inline

For related files that aren't mentioned in the body text but are genuinely relevant, add or update a `## See also` section at the bottom:

```markdown
## See also

- [trust-framework.md](trust-framework.md) — the framework this operationalises
- [trust-neuroscience.md](trust-neuroscience.md) — biological basis for why vulnerability works
```

Rules:
- Only add if the connection is specific and useful — not just "related topic"
- One-line description per link explaining the *nature* of the relationship
- If a `## See also` section already exists, merge — don't duplicate
- Use relative paths (filename only)

---

## Pass 3 — Report

After making all edits, produce a short report:

```
## Curation run — YYYY-MM-DD

Links added: N (across X files)
Orphans remaining: list any files that still have no incoming links
Stubs: list files under 150 words
Overlap candidates: list any pairs worth reviewing for merge
```

Write this report as a dated section in `/wiki/synthesis.md` under a `## Curation YYYY-MM-DD` header (separate from synthesis run headers).
