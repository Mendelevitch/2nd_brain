# Notion integration (optional)

Notion is used to store todos captured by Brain Bot and reviewed during weekly planning.

If you don't need this, leave `NOTION_TOKEN` and `NOTION_DB` empty in `config.py` — the bot will skip all Notion calls silently.

## Create the database

1. Create a new Notion page
2. Add a full-page database (Table view)
3. Set up the following properties:

| Property | Type | Options |
|---|---|---|
| Name | Title | — |
| Status | Status | `Pending Review`, `This Week`, `Postponed`, `Backlog`, `Done` |
| Due Date | Date | — |
| Priority | Select | `🔴 Urgent`, `🟡 High`, `⚪ Normal` |
| Source | Select | `voice`, `text`, `cowork` |

## Create an integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. New integration → give it a name → copy the token
3. Open your database page → `...` menu → Connections → add your integration

## Add to config.py

```python
NOTION_TOKEN = "ntn_..."          # your integration token
NOTION_DB    = "xxxxxxxxxxxxxxxx" # database ID from the page URL
```

The database ID is the 32-character string in the URL:  
`notion.so/workspace/`**`80c3b2b3ae044277986f470604d8c54e`**`?v=...`
