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

## Step 2 — Suggest new todos from insights

Read the most recent file in `/insights/`.
Read all files in `/wiki/`.

Based on the latest digest and the current state of the wiki, propose **3–5 strategic tasks** for the coming week. These should be:
- Concrete actions, not abstract ideas
- Connected to active projects or open questions in the wiki
- Realistically completable in 1–4 hours each
- Things that would move something forward, not just maintenance

Tag each as `[suggested]`.

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

## Step 6 — Done

Git commits are handled automatically via cron. No manual commit needed. Notion changes persist on Notion's side.
