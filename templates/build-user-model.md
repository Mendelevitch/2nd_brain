# Build your user model

Your user model tells the Mind Bot who you are, how you think, and how to talk to you. The more accurate it is, the better the bot.

Pick the path that fits you:

---

## Option A — Let Cowork build it from your brain

Run this prompt in Cowork after your wiki has some content. It reads everything you've captured and writes the model from evidence.

```
Read everything in /raw, /wiki, and /archive. Your job is to build an accurate user model of the person who wrote all of this.

Do not invent anything. Every claim you make should be grounded in something they actually wrote, said, or saved. If you're uncertain — say so. If something is contradictory — flag it.

Be a biographer, not a flatterer. Avoid generic compliments ("curious thinker", "strategic mind"). Use specific language: what domains, what tensions, what recurring patterns, what they explicitly said about themselves.

Write the model in this format and save it to user/user-model.md:

---

# [Name if known] — User Model

## Identity
Who they are. What they do professionally. Where they operate. What role they seem to occupy — founder, operator, creative, advisor, something else.

## Current focus
What they're actively working on right now. Projects, problems, transitions. Use specific names and details from the notes, not summaries.

## How they think
Their cognitive style — do they reason bottom-up or top-down? Do they think in systems or in stories? How do they handle ambiguity? What do they find genuinely interesting vs. professionally relevant? What patterns repeat in how they attack a problem?

## What they care about
Values and obsessions that show up repeatedly. Not stated values — revealed values, the ones that surface when they argue, when they push back, when they get excited.

## Communication preferences
How direct are they? What do they push back on? What kind of answers frustrate them? What do they respond well to? Do they want short answers or developed ones? What did they explicitly ask an AI to do differently?

## Intellectual influences
People, books, disciplines, or ideas they reference. What fields seem to have shaped how they think, even if they don't name them directly.

## Contrarian positions
Things they believe that go against mainstream views in their field or culture. Things they've argued with conviction. Positions that seem personal, not just adopted.

## Blind spots and gaps
What topics are conspicuously absent? What do they seem to avoid or resist? Where does their thinking seem weakest or least developed? Be honest — this is useful.

## What to avoid
Things that frustrate them. Behaviours or responses they've explicitly rejected. Patterns that create friction.

---

Then create a shorter user/user-model-public.md — same structure, but:
- Remove current projects and anything operationally sensitive
- Keep identity, thinking style, communication preferences, intellectual influences
- This version is shown to guests
```

---

## Option B — You've been using ChatGPT or Claude

1. Open a substantial conversation (or export your memory)
2. Paste this prompt:

```
Based on everything you know about me from our conversations, write a structured user model for a personal AI assistant. Be specific — use things I've actually said, not generic descriptions.

Every claim should be grounded in something I've written or said. Flag anything you're guessing at. If there are gaps, note them — I'll fill them in manually.

Structure it like this:

# [My name if you know it] — User Model

## Identity
## Current focus
## How I think
## What I care about
## Communication preferences
## Intellectual influences
## Contrarian positions
## Blind spots and gaps
## What to avoid
```

3. Save the output to `user/user-model.md`
4. Read it — fix anything wrong or outdated
5. Create `user/user-model-public.md` — same structure, remove anything too personal

---

## Option C — Starting from scratch

Open `onboarding-cowork.md` in Cowork. It will interview you directly and write the model from your answers.
