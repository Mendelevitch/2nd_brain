# Import your user model from Claude

If you've been using Claude for a while, it already knows a lot about you. Use this prompt to extract that knowledge into a structured user model for 2ND Brain.

## How to use

1. Open a Claude conversation (ideally one of your longer or more substantive ones)
2. Paste the prompt below
3. Copy the output into `user/user-model.md` in your brain directory

---

## Prompt

```
Based on everything you know about me from our conversations, write a structured user model for a personal AI assistant. Be specific and concrete — use things I've actually said, not generic descriptions.

Structure it exactly like this:

# [My name if you know it, otherwise "User"] — User Model

## Identity
[Who I am, what I do, where I'm based — based on what I've told you]

## Current focus
[Bullet list of projects, problems, or areas I've been actively working on]

## How I think
[My cognitive style. How I approach problems. What I find interesting. What patterns you've noticed in how I reason.]

## Communication preferences
[How direct I am. Whether I prefer short answers or depth. What I push back on. What I respond well to.]

## Intellectual influences
[People, fields, or ideas I reference or seem shaped by]

## Contrarian positions
[Things I believe or have argued that go against mainstream views in my field]

## What to avoid
[Things that frustrate me or that I've explicitly asked you not to do]

Be honest and specific. If you're not sure about something, say so rather than inventing it. If there are gaps, note them — I'll fill them in manually.
```

---

## After you get the output

1. Save it as `user/user-model.md`
2. Read it yourself — correct anything that's wrong or outdated
3. Also create a shorter `user/user-model-public.md` — same structure but remove anything too personal (current projects, specific beliefs, contact info). This version is shown to guests.
