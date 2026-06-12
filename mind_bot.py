import os
import sys
import glob
import json
import logging
import urllib.request
import urllib.parse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from datetime import datetime
import anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import MIND_BOT_TOKEN as TOKEN, ANTHROPIC_API_KEY, OWNER_ID, BRAIN_DIR

# ─── CONFIG ───────────────────────────────────────────────
WIKI_DIR         = os.path.join(BRAIN_DIR, "wiki")
RAW_DIR          = os.path.join(BRAIN_DIR, "raw")
INSIGHTS_DIR     = os.path.join(BRAIN_DIR, "insights")
GUEST_DIR        = os.path.join(BRAIN_DIR, "guest_chats")
USER_MODEL        = os.path.join(BRAIN_DIR, "user/user-model.md")
USER_MODEL_PUBLIC = os.path.join(BRAIN_DIR, "user/user-model-public.md")
GUESTS_FILE       = os.path.join(BRAIN_DIR, "guests.json")

# ─── CLIENT ───────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
logging.basicConfig(level=logging.INFO)

# ─── SESSION STATE ────────────────────────────────────────
sessions = {}
session_saved_length = {}
user_think_mode = {}   # user_id -> bool
user_browse_mode = {}  # user_id -> bool

# ─── GUESTS ───────────────────────────────────────────────
def load_guests():
    if not os.path.exists(GUESTS_FILE):
        return {}
    with open(GUESTS_FILE, "r") as f:
        return json.load(f)

def get_guest_ids():
    return [int(uid) for uid in load_guests().keys()]

def get_guest_name(user_id):
    guests = load_guests()
    return guests.get(str(user_id), str(user_id))

# ─── LOADERS ──────────────────────────────────────────────
def load_user_model(public=False):
    path = USER_MODEL_PUBLIC if public else USER_MODEL
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()

def load_wiki_index():
    """Returns index string: either _index.md contents or fallback snippets."""
    if not os.path.exists(WIKI_DIR):
        return "", []
    index_path = os.path.join(WIKI_DIR, "_index.md")
    all_files = [f for f in sorted(os.listdir(WIKI_DIR)) if f.endswith(".md") and f != "_index.md"]
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            index_text = f.read()
    else:
        lines = []
        for fname in all_files:
            path = os.path.join(WIKI_DIR, fname)
            with open(path, "r") as f:
                snippet = f.read(200).replace("\n", " ")
            lines.append(f"**{fname}** — {snippet}")
        index_text = "\n".join(lines)
    return index_text, all_files

def select_relevant_files(query, index_text, all_files):
    """Pass 1: ask Haiku which wiki files are relevant to the query."""
    if not index_text:
        return []
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system="You are a search assistant. Given a user query and a wiki index, return ONLY the filenames (comma-separated) of files relevant to the query. Return at most 5 files. If none are relevant, return NONE.",
        messages=[{"role": "user", "content": f"Query: {query}\n\nWiki index:\n{index_text}"}]
    )
    result = response.content[0].text.strip()
    if result == "NONE":
        return []
    selected = [f.strip() for f in result.split(",")]
    valid = set(all_files)
    return [f for f in selected if f in valid]

def load_wiki(query=None):
    index_text, all_files = load_wiki_index()
    if not all_files:
        return ""
    if query:
        relevant = select_relevant_files(query, index_text, all_files)
        files_to_load = relevant if relevant else all_files[:3]
    else:
        files_to_load = all_files
    texts = []
    for fname in files_to_load:
        path = os.path.join(WIKI_DIR, fname)
        if os.path.exists(path):
            with open(path, "r") as f:
                texts.append(f"### {fname}\n{f.read()}")
    return "\n\n".join(texts)

def web_search(query, max_results=3):
    """Search DuckDuckGo and return short snippets."""
    try:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "MindBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        results = []
        if data.get("AbstractText"):
            results.append(data["AbstractText"])
        for item in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(item, dict) and item.get("Text"):
                results.append(item["Text"])
        return "\n\n".join(results[:max_results]) if results else ""
    except Exception as e:
        logging.warning(f"web_search failed: {e}")
        return ""

def get_latest_digest():
    if not os.path.exists(INSIGHTS_DIR):
        return None
    files = sorted(glob.glob(os.path.join(INSIGHTS_DIR, "*.md")))
    if not files:
        return None
    with open(files[-1], "r") as f:
        return f.read()

# ─── DIGEST SPLITTER ──────────────────────────────────────
def split_digest(content, max_len=4000):
    """Split digest into chunks by ## sections, respecting Telegram's 4096 char limit."""
    chunks = []
    current = []
    current_len = 0

    for line in content.splitlines(keepends=True):
        is_section = line.startswith("## ")
        # Start new chunk at a section boundary if current is getting long
        if is_section and current_len > max_len // 2 and current:
            chunks.append("".join(current).strip())
            current = []
            current_len = 0
        # If a single line would overflow, force-flush first
        if current_len + len(line) > max_len and current:
            chunks.append("".join(current).strip())
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)

    if current:
        chunks.append("".join(current).strip())
    return [c for c in chunks if c]


# ─── SAVE ─────────────────────────────────────────────────
def save_session(user_id, messages, is_guest=False):
    if not messages:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content = f"source: {'guest_chat' if is_guest else 'chat_extract'}\ndate: {timestamp}\nuser_id: {user_id}\n\n"
    for m in messages:
        role = "Guest" if (is_guest and m["role"] == "user") else ("Misha" if m["role"] == "user" else "Claude")
        content += f"**{role}:** {m['content']}\n\n"
    if is_guest:
        name = get_guest_name(user_id)
        folder = os.path.join(GUEST_DIR, name)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{timestamp}.md")
    else:
        path = os.path.join(RAW_DIR, f"{timestamp}_chat_extract.md")
    with open(path, "w") as f:
        f.write(content)
    session_saved_length[user_id] = len(messages)

# ─── AUTOSAVE ─────────────────────────────────────────────
async def autosave(context):
    for user_id, messages in list(sessions.items()):
        if not messages:
            continue
        already_saved = session_saved_length.get(user_id, 0)
        if len(messages) > already_saved:
            is_guest = user_id in get_guest_ids()
            save_session(user_id, messages, is_guest)

# ─── HANDLER ──────────────────────────────────────────────
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    guest_ids = get_guest_ids()
    if user_id != OWNER_ID and user_id not in guest_ids:
        return

    msg = update.message
    text = msg.text or ""
    is_guest = user_id in guest_ids

    # Ignore unknown commands
    if text.startswith("/") and text not in ["/think", "/browse", "/digest", "/tasks"]:
        return

    # Digest command (owner only)
    if text.lower() in ["дайджест", "digest", "/digest"] and not is_guest:
        content = get_latest_digest()
        if not content:
            await msg.reply_text("No digests yet")
            return
        for chunk in split_digest(content):
            await msg.reply_text(chunk)
        return

    # Toggle think mode (owner only)
    if text == "/think" and not is_guest:
        user_think_mode[user_id] = not user_think_mode.get(user_id, False)
        state = "ON" if user_think_mode[user_id] else "OFF"
        browse_state = "ON" if user_browse_mode.get(user_id, False) else "OFF"
        await msg.reply_text(f"🧠 think: {state}  🌐 browse: {browse_state}")
        return

    # Toggle browse mode (owner only)
    if text == "/browse" and not is_guest:
        user_browse_mode[user_id] = not user_browse_mode.get(user_id, False)
        state = "ON" if user_browse_mode[user_id] else "OFF"
        think_state = "ON" if user_think_mode.get(user_id, False) else "OFF"
        await msg.reply_text(f"🧠 think: {think_state}  🌐 browse: {state}")
        return

    # End session (owner only)
    if text == "??" and not is_guest:
        if user_id in sessions and sessions[user_id]:
            save_session(user_id, sessions[user_id], False)
            sessions.pop(user_id)
            session_saved_length.pop(user_id, None)
            await msg.reply_text("✓ saved to brain")
        else:
            await msg.reply_text("No active session")
        return

    if user_id not in sessions:
        sessions[user_id] = []

    sessions[user_id].append({"role": "user", "content": text})

    user_model = load_user_model(public=is_guest)
    wiki_context = load_wiki() if not is_guest else load_wiki(query=text)

    think_mode = user_think_mode.get(user_id, False) and not is_guest
    browse_mode = user_browse_mode.get(user_id, False) and not is_guest

    web_context = ""
    if browse_mode:
        web_context = web_search(text)

    model = "claude-sonnet-4-6" if think_mode else "claude-haiku-4-5-20251001"

    if is_guest:
        is_first_message = len(sessions[user_id]) == 1
        greeting_instruction = "This is the very first message of the conversation. Greet the person warmly and invite them to share an idea they've been thinking about lately — something they'd like to explore together. Keep it short and open." if is_first_message else ""
        system_blocks = [
            {
                "type": "text",
                "text": f"""You are a sharp thinking partner. You think like Misha — a creative director, brand strategist and systems thinker from London.

Your job is not to answer questions from a database. Your job is to help the guest think better about their ideas — challenge assumptions, find unexpected angles, surface what's really interesting underneath the surface.

How you think:
{user_model[:2000]}

Relevant context and frameworks you can draw on:
{wiki_context}

Rules:
- Never mention "wiki", "knowledge base", "Misha's notes" or any internal system. The guest doesn't know about any of that.
- Don't say "I don't have information on X" — either engage with what you know or ask a question that moves the conversation forward.
- If the guest asks something factual you're uncertain about, engage with the idea first, then note what you'd want to verify.
- Apply Misha's perspective and frameworks to whatever the guest brings up.
- Brainstorm as an equal — build on their ideas, throw in unexpected angles, yes-and and then challenge. This is a creative conversation between two people thinking together, not Q&A.
- Always reply in the same language as the guest's message.
{greeting_instruction}"""
            }
        ]
    elif think_mode:
        web_section = f"\n\nWEB SEARCH RESULTS:\n{web_context}" if web_context else ""
        system_blocks = [
            {
                "type": "text",
                "text": f"You are a wise thinking partner for Misha — a creative director and brand strategist from London.\n\nHis knowledge base is your foundation — you have full access to everything in it:\n\nWIKI — his full knowledge base:\n{wiki_context}",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"USER MODEL:\n{user_model[:3000]}{web_section}\n\nYour role is NOT to answer questions — it is to expand thinking. For each message:\n- Connect the idea to unexpected angles, broader concepts, or contrasting perspectives\n- Ask one sharp question that might shift how Misha sees the problem\n- Surface what might be missing or worth questioning\n- Think out loud, be speculative, bring in ideas from outside his world\n\nBe a sparring partner, not a search engine. Challenge gently. Surprise occasionally. Always reply in the same language as the user's message."
            }
        ]
    else:
        web_section = f"\n\nWEB SEARCH RESULTS:\n{web_context}" if web_context else ""
        system_blocks = [
            {
                "type": "text",
                "text": f"You are Misha's personal assistant — a creative director and brand strategist from London.\n\nWIKI — his full knowledge base:\n{wiki_context}",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"USER MODEL — who Misha is and how he thinks:\n{user_model[:3000]}{web_section}\n\nBe concise and direct. Always reply in the same language as the user's message."
            }
        ]

    thinking_msg = await msg.reply_text("…")

    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system=system_blocks,
        messages=sessions[user_id]
    )

    reply = response.content[0].text
    sessions[user_id].append({"role": "assistant", "content": reply})
    await thinking_msg.edit_text(reply)
    # Log cache usage for cost monitoring
    u = response.usage
    logging.info(f"tokens: input={u.input_tokens} cache_read={getattr(u, 'cache_read_input_tokens', 0)} cache_write={getattr(u, 'cache_creation_input_tokens', 0)} output={u.output_tokens}")

# ─── RUN ──────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle))
    app.job_queue.run_repeating(autosave, interval=1800, first=1800)
    app.run_polling()
