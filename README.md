# 2ND Brain

A personal second brain running on a Raspberry Pi — two Telegram bots, a local wiki synced to your Mac, and a set of Cowork prompts that process everything weekly.

```
You → Telegram → SaveBot → /raw → Cowork → /wiki → ChatBot → You
```

**SaveBot** captures everything: voice memos, photos, links, documents, forwarded messages.  
**ChatBot** lets you have a conversation with your own knowledge base — including in Telegram group chats.

---

## What it does

- **Voice** → transcribed via Whisper → categorised → saved
- **Photo** → OCR'd via Claude Vision → saved as text
- **Link** → scraped (markitdown first, newspaper3k fallback) → saved
- **Document** (PDF, DOCX, XLSX…) → converted to markdown → saved
- **Text** → categorised into `idea / thought / todo / event / case / link / cool / question / reference`
- **Forwarded messages** → saved with author attribution, scanned for action items

**ChatBot** features:
- Two-pass wiki search (index scan → full file load) across `/wiki` and `/projects`
- Group chat support — @mention the bot in a group; it remembers context across the conversation
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

- A Linux server — Raspberry Pi 4/5, or a VPS (DigitalOcean, Hetzner, etc.)
- Python 3.11+
- Telegram account
- Anthropic API key (for the bots)
- OpenAI API key (optional — for voice transcription via Whisper)

**For automatic wiki processing:** [Cowork](https://cowork.ai) on a Mac/PC, synced via Syncthing. Without it, the bots still work — capture and chat — but wiki won't update automatically.

---

## Quick start

```bash
git clone https://github.com/yourusername/2nd-brain.git
cd 2nd-brain && ./install.sh
```

That's it. The script asks for your API keys and bot tokens, creates the brain directory, installs dependencies, and starts both bots as systemd services.

### 3. Install dependencies

```bash
pip3 install python-telegram-bot[job-queue] openai anthropic \
             newspaper3k lxml_html_clean yt-dlp \
             "markitdown[all]" --break-system-packages
```

### 4. Build your user model

See `templates/build-user-model.md` — three paths depending on your situation: used ChatGPT before, used Claude before, or starting fresh. Then run `templates/onboarding-cowork.md` in Cowork to seed your wiki.

### 5. Install as services (Raspberry Pi)

```bash
# Edit services/*.service — replace /path/to/your/brain/_Claude with your actual path
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable save-bot chat-bot watch-bots
sudo systemctl start save-bot chat-bot watch-bots
```

### 6. Set up Syncthing (optional, Mac/Pi only)

---

## Deploy to VPS (DigitalOcean / Hetzner)

No Raspberry Pi? A $6/month VPS works just as well.

### 1. Create a server

DigitalOcean Droplet or Hetzner CX22 — Ubuntu 24.04, 2GB RAM minimum.

### 2. Set up the brain directory

```bash
mkdir -p ~/brain/{raw,wiki,archive,insights,user,guest_chats,chats,prompts,skills,_Claude}
```

### 3. Clone and configure

```bash
git clone https://github.com/yourusername/2nd-brain.git
cd 2nd-brain
cp config.example.py config.py
nano config.py  # fill in your tokens and set BRAIN_DIR="/root/brain"
cp -r prompts/* ~/brain/prompts/
cp save_bot.py chat_bot.py ~/brain/_Claude/
```

### 4. Install dependencies

```bash
pip3 install python-telegram-bot[job-queue] openai anthropic \
             newspaper3k lxml_html_clean yt-dlp \
             "markitdown[all]" --break-system-packages
```

### 5. Install as services

```bash
# Edit the paths in service files first
sed -i 's|/path/to/your/brain|/root/brain|g' services/*.service
sudo cp services/save-bot.service services/chat-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable save-bot chat-bot
sudo systemctl start save-bot chat-bot
```

### 6. Build your user model

Create `~/brain/user/user-model.md` — see `templates/user-model.md` for the template. Fill it in manually or use `templates/build-user-model.md` with Cowork.

### What works without Cowork

| Feature | Works |
|---|---|
| Capture (voice, photos, links, text) | ✅ |
| Chat with bot | ✅ |
| Guest access | ✅ |
| YouTube transcription | ✅ |
| Wiki auto-update from raw | ❌ needs Cowork |
| Weekly planning digest | ❌ needs Cowork |

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
├── save_bot.py
├── chat_bot.py
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

## Group chats

Add the Mind Bot to any Telegram group — it will listen silently and respond when @mentioned.

**Important:** by default Telegram's Privacy Mode is enabled, which means the bot only sees @mentions and `/commands` — and only in groups it was added to *after* you turn it off. You need to disable it:

1. Open @BotFather
2. `/mybots` → select your Mind Bot → Bot Settings → Group Privacy → **Turn off**
3. Remove the bot from any existing groups and re-add it (or make it admin)

Without this step the bot will appear to work in some groups but not others.

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

| Prompt | Schedule | What it does |
|---|---|---|
| `prompts/translate.md` | Hourly / after capturing | Processes `/raw` into wiki entries |
| `prompts/research.md` | Every Monday ~2:00 | Finds gaps in the wiki, researches and fills them |
| `prompts/weekly-planning.md` | Every Monday ~9:30 | Reviews todos, suggests the week's tasks |
| `prompts/wiki-curate.md` | Every Friday | Strengthens links between wiki pages |
| `prompts/synthesize.md` | On demand | Cross-wiki synthesis — finds patterns, tensions, and evolutions across all entries |
| `prompts/weekly-thinking-digest.md` | Every Friday ~12:00 | Friday evening digest — surfaces interesting ideas, unexpected intersections, and patterns from the week's wiki entries |

To create all routines at once, run `templates/setup-cowork-routines.md` in Cowork.

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
├── save_bot.py            ← capture bot
├── chat_bot.py            ← chat bot (private + group chats)
├── config.example.py      ← configuration template
├── watch_bots.sh          ← auto-restarts bots on file change
├── requirements.txt
├── services/              ← systemd service files
├── prompts/               ← Cowork process prompts
├── templates/
│   ├── build-user-model.md     ← start here: ChatGPT / Claude / fresh
│   ├── onboarding-cowork.md    ← Cowork setup prompt (seeds wiki)
│   ├── user-model.md           ← blank user model template
│   └── guests.example.json
└── docs/
    ├── setup-syncthing.md
    └── setup-notion.md
```

---

## Backlog

### Pending
- **Shared wiki** — multiple people contributing to and reading from one wiki. Complex architecture problem; leaving as a future idea.

### Done
- ~~Syncthing in install.sh~~ — `install.sh` now offers Syncthing setup, installs it, and prints Device ID
- ~~Cowork routines setup guide~~ — `templates/setup-cowork-routines.md` — run once in Cowork to create all scheduled routines
- ~~Privacy Mode docs~~ — added to README (Group chats section)
- ~~Personalisation removed~~ — all "owner name" references stripped from public repo

---

## Licence

MIT
