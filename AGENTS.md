# Instructions for Cowork Agents

You are working in a personal second brain — a knowledge management system, not a code project. Your job is to keep the wiki current, useful, and well-organized based on the raw notes the user captures.

---

## Folder Structure

```
brain/
├── raw/          ← inbox: everything captured by SaveBot lands here
├── wiki/         ← processed knowledge, one concept per file
├── archive/      ← raw files after processing (permanent record)
├── projects/     ← active projects, one subfolder per project
├── insights/     ← weekly digests and planning outputs
├── user/         ← user-model.md and user-model-public.md
├── chats/        ← group chat transcripts by chat name
├── guest_chats/  ← conversations guests had with the bot
├── prompts/      ← Cowork process prompts (translate, planning, etc.)
├── skills/       ← reusable skill files (.skill, .md)
├── _Claude/      ← bot code, config, and these instructions (not your concern)
├── CLAUDE.md     ← instructions for Claude Code (Pi maintenance)
├── AGENTS.md     ← this file
└── README.md     ← one-paragraph overview of the system
```

**Syncthing directions:**
- `raw/`, `chats/`, `guest_chats/` — Pi → Mac (Pi writes, Mac reads)
- `wiki/`, `insights/`, `user/`, `prompts/`, `skills/` — Mac → Pi (Cowork writes, Pi reads)
- `archive/` — Pi only (not synced)

---

## Before Anything Else

1. Read `README.md` — one-paragraph overview.
2. Read `/user/user-model.md` — who Misha is, how he thinks. Use this to interpret ambiguous notes and set the right tone.

---

## Common Tasks

- **Translate raw** → run `prompts/translate.md` against `/raw`
- **Weekly planning** → run `prompts/weekly-planning.md`
- **Wiki curation** → run `prompts/wiki-curate.md`
- **Project digest** → summarize a `/projects/<name>/` folder into its README
- **Update user model** → update `/user/user-model.md` with changelog entry

---

## Hard Rules

1. **Never delete** anything from `/raw` or `/archive`. Move only, never delete.
2. **Never overwrite** a `/wiki` entry blindly. Always read it first, then merge.
3. **Never modify** `/archive` after a file lands there — it is a permanent record.
4. **Commit after meaningful changes** with a clear message (e.g. `translate: 4 raw files processed`).
5. **When uncertain, log it in the entry** rather than guessing.

---

## Wiki Voice and Structure

- Default tone: clear, factual, terse.
- Preserve Misha's own phrasing when it carries signal — don't neutralize into encyclopedia tone.
- Headings only when the entry is long enough to need them.
- Bullets only when the content is genuinely a list.
- One topic per file. Kebab-case filenames.

---

## Out of Scope

- Web browsing unless explicitly asked.
- External API calls outside of declared automations.
- Anything touching accounts, payments, or auth.
- Editing files in `/raw` or `/archive`.
- Touching anything in `/_Claude/` — that's bot infrastructure.
