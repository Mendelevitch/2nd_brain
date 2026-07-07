# Weekly Planning Prompt

Run this prompt at the start of each week (Monday morning) in Cowork.
It collects todos, suggests new ones from insights, presents them for review, schedules approved tasks in Google Calendar, and writes them to the Notion Tasks database.

**Tasks live in Notion** (not `tasks.md`, which is deprecated/archived).
- Database ID: `80c3b2b3ae044277986f470604d8c54e`
- Fields: `Name` (task text), `Status` (`Pending Review` / `This Week` / `Backlog` / `Done`), `Due Date` (date), `Source` (`voice` / `text` / `cowork`).
- When Cowork creates a task itself, set `Source: cowork`.

---

## Step 1 — Collect todos from Notion

Query the Notion Tasks database (`80c3b2b3ae044277986f470604d8c54e`) for tasks that need attention this week:

**Group A — New captures** (`Status: Pending Review`)
Tasks captured by the bot since last Monday. Tag as `[captured]`.

**Group B — Unfinished from last week** (`Status: This Week`, `Status: Postponed`, not `Done`)
Tasks that were scheduled but not completed. Tag as `[carry-over]`.

Do not include tasks with `Status: Backlog` unless they have a `Due Date` falling this week.

For each task note: Name, Due Date (if set), Source.

## Step 2 — Suggest new todos from insights AND the five-year plan

Read the most recent file in `/insights/`.
Read all files in `/wiki/`.
Read `wiki/five-year-plan-2026-2031.md` (current phase, checkpoints, «Ближайшие 14 дней»), `wiki/strategic-bets-2026.md` (Horizon 1), and the most recent file in `projects/five-year-plan/weekly/` (what was done / not done last week).

Propose **3–7 strategic tasks** for the coming week, organized into the four plan sections:

- **Якорь (Flo):** progress toward the Social Lead role / anchor income.
- **Side-двигатель:** InLab, sprints, тёплые интро, outreach drafts.
- **Категория:** the topic for this week's post (suggest a concrete one from wiki: trust framework, LLM visibility, Reddit) — for the Wednesday 10:00 slot.
- **Семья и здоровье:** from the plan (финансовый час, fertility/анализы, виза отца, ужин — приглашения за 2 недели до третьего четверга). **This section is never empty** (plan rule 5).

Tasks must be: concrete actions, completable in 1–4 hours, moving a plan milestone forward — not maintenance.

Tag each as `[suggested]`. Carry-over tasks keep a counter: «(2-я неделя)», «(3-я неделя)» — three weeks in a row = a question for the monthly check-in, not a guilt trip.

## Step 3 — Present for review

Show the user the combined list:

```
Задачи на неделю:

[captured]
1. <task text> (от <date>)
2. ...

[carry-over]
3. <task> (не сделано с прошлой недели)
...

[suggested]
4. <task>
5. ...

Какие берём? Напиши номера через запятую.
Для каждой укажи сколько времени (н: "1:2ч, 3:1ч").
Остальные перенесём в Backlog автоматически.
Или /skip чтобы пропустить всё.
```

Wait for the user's response. If they skip, stop here.

## Step 4 — Schedule in Google Calendar

For each approved task with a time estimate:

1. Check Google Calendar for the coming week (Mon–Fri, 10:00–19:00).
2. Find a free slot matching the estimated duration. Prefer mornings for deep work tasks.
3. Create a calendar event:
   - Title: task text
   - Duration: as specified
   - Description: source tag + original date if [captured]
4. Note the event ID.

## Step 5 — Create tasks in Notion

For each approved task, create a page in the Notion Tasks database (`80c3b2b3ae044277986f470604d8c54e`):
- `Name` = task text
- `Source` = `cowork`
- If it has a calendar event → `Status: This Week`, set `Due Date` to the event date/time.
- If no time estimate was given → `Status: Backlog` (leave `Due Date` empty).

For tasks that were **not approved** (skipped by the user):
- Set `Status: Postponed` — they'll surface again next Monday as `[carry-over]`.

Note: `Status` field values: `Pending Review` / `This Week` / `Postponed` / `Backlog` / `Done`.

## Step 6 — Write the weekly plan file

Write the final week plan to `projects/five-year-plan/weekly/YYYY-Wnn.md` (ISO week number): the approved tasks grouped by the four sections (Якорь / Side-двигатель / Категория / Семья и здоровье), with carry-over counters and the chosen post topic. One page max. Clear, factual, no motivational filler. This file is the input for the monthly check-in summary (`monthly-goals-checkin`).

## Step 7 — Done

Git commits are handled automatically via cron. No manual commit needed. Notion changes persist on Notion's side.
