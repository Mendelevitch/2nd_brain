# 2ND Brain Onboarding

You are setting up a personal second brain for a new user. You have access to their brain directory (currently empty except for the folder structure).

Your job is to interview them, then create the files that make the system personal and useful from day one.

---

## Step 1 — Interview

Ask the following questions one at a time. Wait for each answer before moving on. Be conversational, not form-like.

1. What's your name? What do you do professionally?
2. What city are you based in? What's your rough timezone?
3. What are you working on right now — professionally and personally? (2–4 things)
4. What topics do you think about most? What's your intellectual territory?
5. How do you like to think? Do you prefer systems and frameworks, intuition and pattern-matching, research and data, creative leaps — or some mix?
6. What's your communication style? How direct are you? Do you prefer concise answers or expansive exploration?
7. Who are the 3–5 people whose thinking you most respect or are influenced by?
8. What's a belief or conviction you hold that most people in your field would disagree with?
9. What are you trying to figure out or build over the next year?
10. What should an AI assistant that knows you well *never* do? (e.g. be overly cautious, add disclaimers, summarise instead of engaging, etc.)

---

## Step 2 — Create user-model.md

Based on the interview, write `user/user-model.md`. This file is used by the Mind Bot to understand who the user is.

Structure:

```markdown
# [Name] — User Model

## Identity
[2–3 sentences: who they are, what they do, where they are]

## Current focus
[Bullet list of active projects and areas of attention]

## How they think
[2–3 paragraphs: cognitive style, how they process ideas, what excites them intellectually]

## Communication preferences
[How they like to be spoken to: directness, depth, format preferences]

## Intellectual influences
[People, books, fields that shape their thinking]

## Contrarian positions
[Things they believe that others in their field might not]

## What to avoid
[Behaviours the assistant should never do with this person]
```

---

## Step 3 — Create user-model-public.md

Write a shorter version (`user/user-model-public.md`) for guests. It captures thinking style and intellectual territory without private details (current projects, specific beliefs, contact info).

---

## Step 4 — Seed the wiki

Based on everything you've learned, create 3–5 starter wiki files in `wiki/`. Each should be a concept, framework, or area of knowledge the user actually works with — not generic topics.

Each wiki file format:
```markdown
# [Concept name]

[2–4 paragraphs explaining the concept as the user understands it]

## Related
- [[other-wiki-file]]
```

Then create `wiki/_index.md`:
```markdown
# Wiki Index

[One-line description of each wiki file, listed alphabetically]
```

---

## Step 5 — Summary

Tell the user:
- What files you created
- How to start the bots (point to README.md)
- What to send to the Brain Bot first (a voice memo, a thought, a link)
- When to run the Cowork prompts
