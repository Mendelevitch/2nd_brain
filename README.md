# 2ND Brain

A personal second brain running on a Raspberry Pi — two Telegram bots, a local wiki synced to your Mac, and a set of Cowork prompts that process everything weekly.

```
You → Telegram → Brain Bot → /raw → Cowork → /wiki → Mind Bot → You
```

**Brain Bot** captures everything: voice memos, photos, links, documents, forwarded messages.  
**Mind Bot** lets you have a conversation with your own knowledge base.

---

## What it does

- **Voice** → transcribed via Whisper → categorised → saved
- **Photo** → OCR'd via Claude Vision → saved as text
- **Link** → scraped (markitdown first, newspaper3k fallback) → saved
- **Document** (PDF, DOCX, XLSX…) → converted to markdown → saved
- **Text** → categorised into `idea / thought / todo / event / case / link / cool / question / reference`
- **Forwarded messages** → saved with author attribution, scanned for action items

**Mind Bot** features:
- Two-pass wiki search (index scan → full file load)
- `/think` — deeper mode using Claude Sonnet, acts as a sparring partner
- `/browse` — adds DuckDuckGo results to context
- Guest mode — friends get their own conversation channel with your bot
- `??` — saves and closes the session
- `дайджест` / `digest` — sends the latest weekly digest

**Cowork prompts** (run weekly on your Mac):
- `translate.md` — processes `/raw` into wiki entries
- `wiki-curate.md` — strengthens links between wiki pages
- `weekly-planning.md` — reviews todos, suggests next steps

---

## Requirements

- Raspberry Pi 4 or 5 (2 GB+ RAM)
- Python 3.11+
- A Mac or PC synced via Syncthing (optional but recommended)
- Cowork or Claude.ai for running the weekly prompts
- Telegram account

---

## Quick start

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/2nd-brain.git
cd 2nd-brain
cp config.example.py config.py
# Edit config.py — fill in all values (see comments in the file)
```

### 2. Create your brain directory

```bash
mkdir -p /path/to/your/brain/{raw,wiki,archive,insights,user,guest_chats,prompts}
cp prompts/* /path/to/your/brain/prompts/
```

### 3. Install dependencies

```bash
pip3 install python-telegram-bot[job-queue] openai anthropic \
             newspaper3k lxml_html_clean yt-dlp \
             "markitdown[all]" --break-system-packages
```

### 4. Run the onboarding prompt

Open `templates/onboarding-cowork.md` in Cowork (or Claude.ai) and point it at your brain directory. It will interview you and create your `user-model.md`.

### 5. Install as services (Raspberry Pi)

```bash
# Edit services/*.service — replace /mnt/hdd/Misha_pi/brain/_Claude with your path
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable brain-bot mind-bot watch-bots
sudo systemctl start brain-bot mind-bot watch-bots
```

### 6. Set up Syncthing (optional)

See [docs/setup-syncthing.md](docs/setup-syncthing.md).

---

## Architecture

```
Telegram
├── Brain Bot  — captures everything → /raw
└── Mind Bot   — conversation with your brain → reads /wiki + /user

Raspberry Pi
├── /brain/
│   ├── raw/          ← Brain Bot writes here
│   ├── wiki/         ← Cowork processes raw → wiki
│   ├── archive/      ← processed raw + original documents
│   ├── projects/     ← active projects
│   ├── insights/     ← weekly digests
│   ├── guest_chats/  ← Mind Bot guest conversations
│   └── user/         ← user-model.md, user-model-public.md
├── brain_bot.py
├── mind_bot.py
└── config.py         ← your secrets (gitignored)

Mac (via Syncthing)
├── raw/      ← Pi → Mac
├── wiki/     ← Mac → Pi
├── insights/ ← Mac → Pi
└── user/     ← Mac → Pi

Cowork (on Mac)
└── reads brain/, processes raw → wiki, generates insights
```

---

## Guest mode

Add friends to `guests.json`:

```json
{
  "123456789": "Alice",
  "987654321": "Bob"
}
```

Guests get their own conversation channel with your Mind Bot. The bot uses your wiki and thinking style, but presents itself as a thinking partner — never mentions your notes or internal system.

---

## Cowork prompts

| Prompt | When to run | What it does |
|---|---|---|
| `prompts/translate.md` | Daily or after capturing | Processes `/raw` into wiki entries |
| `prompts/wiki-curate.md` | Weekly | Strengthens links between wiki pages |
| `prompts/weekly-planning.md` | Monday morning | Reviews todos, suggests the week's tasks |

---

## API keys needed

| Key | Where to get | Required? |
|---|---|---|
| Anthropic | [console.anthropic.com](https://console.anthropic.com/settings/keys) | Yes |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | For voice transcription |
| Telegram (×2) | [@BotFather](https://t.me/BotFather) | Yes |
| Notion | [notion.so/my-integrations](https://www.notion.so/my-integrations) | Optional |

---

## Folder structure

```
2nd-brain/
├── brain_bot.py           ← capture bot
├── mind_bot.py            ← chat bot
├── config.example.py      ← configuration template
├── watch_bots.sh          ← auto-restarts bots on file change
├── requirements.txt
├── services/              ← systemd service files
├── prompts/               ← Cowork process prompts
├── templates/
│   ├── onboarding-cowork.md       ← setup prompt for Cowork
│   ├── onboarding-chatgpt.md      ← setup prompt for ChatGPT
│   ├── user-model.md              ← blank user model template
│   └── guests.example.json
└── docs/
    ├── setup-syncthing.md
    └── setup-notion.md
```

---

## Licence

MIT
