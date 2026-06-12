# Build your user model

Your user model tells the Mind Bot who you are, how you think, and how to talk to you. The more accurate it is, the better the bot.

Pick the path that fits you:

---

## Option A — You've been using ChatGPT

1. Open any substantial ChatGPT conversation
2. Paste the prompt below
3. Copy the output into `user/user-model.md`

## Option B — You've been using Claude

1. Open any substantial Claude conversation
2. Paste the prompt below
3. Copy the output into `user/user-model.md`

## Option C — Starting fresh

Open `onboarding-cowork.md` in Cowork and point it at your brain directory. It will interview you and fill everything in.

---

## The prompt (for Options A and B)

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
2. Read it — correct anything wrong or outdated
3. Create a shorter `user/user-model-public.md` — same structure, but remove anything too personal (current projects, specific beliefs). This version is shown to guests.
