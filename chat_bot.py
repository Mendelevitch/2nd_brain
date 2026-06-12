import os
import sys
import re
import glob
import json
import logging
import urllib.request
import urllib.parse
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from datetime import datetime
import anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import MIND_BOT_TOKEN as TOKEN, ANTHROPIC_API_KEY, OWNER_ID, BRAIN_DIR

# ─── CONFIG ───────────────────────────────────────────────
WIKI_DIR          = os.path.join(BRAIN_DIR, "wiki")
PROJECTS_DIR      = os.path.join(BRAIN_DIR, "projects")
RAW_DIR           = os.path.join(BRAIN_DIR, "raw")
INSIGHTS_DIR      = os.path.join(BRAIN_DIR, "insights")
GUEST_DIR         = os.path.join(BRAIN_DIR, "guest_chats")
CHATS_DIR         = os.path.join(BRAIN_DIR, "chats")
USER_MODEL        = os.path.join(BRAIN_DIR, "user/user-model.md")
USER_MODEL_PUBLIC = os.path.join(BRAIN_DIR, "user/user-model-public.md")
GUESTS_FILE       = os.path.join(BRAIN_DIR, "guests.json")
GROUP_STATE_FILE  = os.path.join(BRAIN_DIR, "chats/.state.json")

# ─── CLIENT ───────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
logging.basicConfig(level=logging.INFO)

# ─── SESSION STATE ────────────────────────────────────────
sessions = {}
session_saved_length = {}
user_think_mode = {}   # user_id -> bool
user_browse_mode = {}  # user_id -> bool

# ─── GROUP STATE ──────────────────────────────────────────
group_buffers = {}   # chat_id → [{"author", "text", "msg_id", "ts"}]
group_state = {}     # chat_id → {"name": str, "last_processed_id": int}
group_members = {}   # chat_id → set of known member names
group_sessions = {}   # chat_id → [{"role", "content"}] — conversation with bot
group_think = {}      # chat_id → bool
group_browse = {}     # chat_id → bool

def chat_folder_name(title):
    return re.sub(r'[^\w-]', '-', title.strip().lower()).strip('-') or "group"

def load_group_state():
    global group_state
    if os.path.exists(GROUP_STATE_FILE):
        with open(GROUP_STATE_FILE) as f:
            group_state = {int(k): v for k, v in json.load(f).items()}

def save_group_state():
    os.makedirs(os.path.dirname(GROUP_STATE_FILE), exist_ok=True)
    with open(GROUP_STATE_FILE, "w") as f:
        json.dump(group_state, f)

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

def collect_all_files():
    """Returns list of (label, abs_path) for wiki + all project files."""
    entries = []
    # wiki files
    if os.path.exists(WIKI_DIR):
        for fname in sorted(os.listdir(WIKI_DIR)):
            if fname.endswith(".md") and fname not in ("_index.md", ".gitkeep"):
                entries.append((fname, os.path.join(WIKI_DIR, fname)))
    # projects — walk subdirectories
    if os.path.exists(PROJECTS_DIR):
        for root, dirs, files in os.walk(PROJECTS_DIR):
            dirs[:] = [d for d in sorted(dirs) if not d.startswith('.')]
            for fname in sorted(files):
                if fname.endswith(".md") and not fname.startswith('.'):
                    rel = os.path.relpath(os.path.join(root, fname), PROJECTS_DIR)
                    entries.append((f"projects/{rel}", os.path.join(root, fname)))
    return entries

def load_wiki_index():
    """Returns (index_text, entries_dict) across wiki + projects."""
    entries = collect_all_files()
    if not entries:
        return "", {}, []

    entries_dict = {label: path for label, path in entries}
    all_labels = list(entries_dict.keys())

    index_path = os.path.join(WIKI_DIR, "_index.md")
    wiki_index = open(index_path).read() if os.path.exists(index_path) else ""

    project_lines = []
    for label, path in entries:
        if label.startswith("projects/"):
            with open(path, "r") as f:
                snippet = f.read(200).replace("\n", " ")
            project_lines.append(f"**{label}** — {snippet}")

    index_text = wiki_index
    if project_lines:
        index_text += "\n\n### Active projects\n" + "\n".join(project_lines)

    return index_text, entries_dict, all_labels

def select_relevant_files(query, index_text, all_labels):
    """Pass 1: ask Haiku which files are relevant to the query."""
    if not index_text:
        return []
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system="You are a search assistant. Given a user query and a file index, return ONLY the filenames (comma-separated) of files relevant to the query. Return at most 5 files. If none are relevant, return NONE.",
        messages=[{"role": "user", "content": f"Query: {query}\n\nIndex:\n{index_text}"}]
    )
    result = response.content[0].text.strip()
    if result == "NONE":
        return []
    selected = [f.strip() for f in result.split(",")]
    valid = set(all_labels)
    return [f for f in selected if f in valid]

def load_wiki(query=None):
    index_text, entries_dict, all_labels = load_wiki_index()
    if not all_labels:
        return ""
    if query:
        relevant = select_relevant_files(query, index_text, all_labels)
        files_to_load = relevant if relevant else all_labels[:3]
    else:
        files_to_load = all_labels
    texts = []
    for label in files_to_load:
        path = entries_dict.get(label)
        if path and os.path.exists(path):
            with open(path, "r") as f:
                texts.append(f"### {label}\n{f.read()}")
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

    if web_context:
        web_extra = f"\n\nWEB SEARCH RESULTS:\n{web_context}"
    elif browse_mode:
        web_extra = "\n\nWEB SEARCH: returned no results — do not claim to be browsing."
    else:
        web_extra = ""

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
        system_blocks = [
            {
                "type": "text",
                "text": f"You are a wise thinking partner for Misha — a creative director and brand strategist from London.\n\nHis knowledge base is your foundation — you have full access to everything in it:\n\nWIKI — his full knowledge base:\n{wiki_context}",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"USER MODEL:\n{user_model[:3000]}{web_extra}\n\nYour role is NOT to answer questions — it is to expand thinking. For each message:\n- Connect the idea to unexpected angles, broader concepts, or contrasting perspectives\n- Ask one sharp question that might shift how Misha sees the problem\n- Surface what might be missing or worth questioning\n- Think out loud, be speculative, bring in ideas from outside his world\n\nBe a sparring partner, not a search engine. Challenge gently. Surprise occasionally. Always reply in the same language as the user's message."
            }
        ]
    else:
        system_blocks = [
            {
                "type": "text",
                "text": f"You are Misha's personal assistant — a creative director and brand strategist from London.\n\nWIKI — his full knowledge base:\n{wiki_context}",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"USER MODEL — who Misha is and how he thinks:\n{user_model[:3000]}{web_extra}\n\nBe concise and direct. Always reply in the same language as the user's message."
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

# ─── GROUP CHAT ───────────────────────────────────────────
async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Reply to @mention in group using wiki + public user model + recent chat history."""
    thinking = await update.message.reply_text("…")
    chat_id = update.effective_chat.id

    # Build wiki query from full session context, not just current message
    session_text = " ".join(m["content"] for m in group_sessions.get(chat_id, [])[-50:])
    wiki_query = f"{session_text} {query}".strip()
    wiki = load_wiki(query=wiki_query)
    user_model = load_user_model(public=True)

    # Build recent conversation context (last 20 messages before the mention)
    recent = group_buffers.get(chat_id, [])[-20:]
    chat_history = "\n".join(f"{m['author']}: {m['text']}" for m in recent) if recent else ""
    members = sorted(group_members.get(chat_id, set()))
    members_line = f"People in this chat: {', '.join(members)}" if members else ""

    # Handle toggles
    if query.strip() == "/think":
        group_think[chat_id] = not group_think.get(chat_id, False)
        await thinking.edit_text(f"🧠 think: {'ON' if group_think[chat_id] else 'OFF'}  🌐 browse: {'ON' if group_browse.get(chat_id) else 'OFF'}")
        return
    if query.strip() == "/browse":
        group_browse[chat_id] = not group_browse.get(chat_id, False)
        await thinking.edit_text(f"🧠 think: {'ON' if group_think.get(chat_id) else 'OFF'}  🌐 browse: {'ON' if group_browse[chat_id] else 'OFF'}")
        return

    # Detect language from query (which has the @mention stripped)
    # Fall back to chat history if query has no Cyrillic (e.g. empty or slash command)
    sample = (query or "")[:200] or chat_history[:200]
    lang_instruction = "Reply in Russian." if any(
        'Ѐ' <= c <= 'ӿ' for c in sample
    ) else "Reply in the same language as the user's message."

    web_context = ""
    if group_browse.get(chat_id):
        web_context = web_search(query or chat_history[:100])
    if web_context:
        web_section = f"\n\nWEB SEARCH RESULTS:\n{web_context}"
    elif group_browse.get(chat_id):
        web_section = "\n\nWEB SEARCH: returned no results — do not claim to be browsing."
    else:
        web_section = ""

    system = f"""You are a sharp thinking partner participating in a group chat.
You think like the person described below. You are aware of the ongoing conversation and who is present.
Help the group think better — challenge assumptions, find unexpected angles, brainstorm as an equal.
Never mention "wiki", "knowledge base", "notes", or any internal system.
{lang_instruction}
{members_line}

User model:
{user_model[:2000]}

Relevant knowledge:
{wiki}{web_section}"""

    if chat_id not in group_sessions:
        group_sessions[chat_id] = []

    # First message in session includes recent chat history as context
    if not group_sessions[chat_id] and chat_history:
        user_content = f"Recent chat context:\n{chat_history}\n\n{query or 'What do you think?'}"
    else:
        user_content = query or "What do you think?"

    group_sessions[chat_id].append({"role": "user", "content": user_content})
    # Keep last 20 exchanges
    if len(group_sessions[chat_id]) > 40:
        group_sessions[chat_id] = group_sessions[chat_id][-40:]

    model = "claude-sonnet-4-6" if group_think.get(chat_id) else "claude-haiku-4-5-20251001"
    response = client.messages.create(
        model=model,
        max_tokens=800,
        system=system,
        messages=group_sessions[chat_id]
    )
    reply = response.content[0].text
    group_sessions[chat_id].append({"role": "assistant", "content": reply})
    await thinking.edit_text(reply)

async def scan_group_chat(context):
    """Hourly job: extract action items, links, ideas from group buffers."""
    for chat_id, messages in list(group_buffers.items()):
        state = group_state.get(chat_id, {"name": str(chat_id), "last_processed_id": 0})
        last_id = state["last_processed_id"]
        new_messages = [m for m in messages if m["msg_id"] > last_id]
        if len(new_messages) < 3:
            continue
        batch = new_messages[-100:]
        transcript = "\n".join(f"[{m['ts']}] {m['author']}: {m['text']}" for m in batch)
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": f"""Extract valuable items from this chat transcript.
Return JSON only — skip small talk and noise.

{{"todos": [{{"title": "...", "author": "..."}}], "links": [{{"url": "...", "context": "..."}}], "ideas": [{{"text": "...", "author": "..."}}]}}

Transcript:
{transcript}"""}]
            )
            raw = response.content[0].text.strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                continue
            extracted = json.loads(match.group(0))
        except Exception as e:
            logging.warning(f"scan_group_chat failed for {chat_id}: {e}")
            continue

        chat_name = state["name"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_str = datetime.now().strftime("%Y-%m-%d")

        chat_dir = os.path.join(CHATS_DIR, chat_name)
        os.makedirs(chat_dir, exist_ok=True)
        log_path = os.path.join(chat_dir, f"{date_str}.md")
        with open(log_path, "a") as f:
            f.write(f"\n## Scan {timestamp}\n\n")
            for todo in extracted.get("todos", []):
                f.write(f"- [ ] **{todo['author']}**: {todo['title']}\n")
            for idea in extracted.get("ideas", []):
                f.write(f"- 💡 **{idea['author']}**: {idea['text']}\n")
            for link in extracted.get("links", []):
                f.write(f"- 🔗 {link['url']} — {link['context']}\n")

        items = extracted.get("ideas", []) + extracted.get("links", [])
        if items:
            combined = "\n".join(
                f"{x.get('author','')}: {x.get('text') or x.get('url','')}" for x in items
            )
            content = f"category: idea\nsource: group_chat\nchat: {chat_name}\ndate: {timestamp}\n\n{combined}"
            with open(os.path.join(RAW_DIR, f"{timestamp}_group_idea.md"), "w") as f:
                f.write(content)

        group_state[chat_id]["last_processed_id"] = batch[-1]["msg_id"]
        save_group_state()
        logging.info(f"scan_group_chat [{chat_name}]: {len(extracted.get('todos',[]))} todos, {len(extracted.get('ideas',[]))} ideas")

async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in group/supergroup chats."""
    msg = update.message
    if not msg or not msg.text:
        return

    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or str(chat_id)
    chat_name = chat_folder_name(chat_title)
    author = update.effective_user.full_name or "unknown"
    text = msg.text

    if chat_id not in group_buffers:
        group_buffers[chat_id] = []
        if chat_id not in group_state:
            group_state[chat_id] = {"name": chat_name, "last_processed_id": 0}
    if chat_id not in group_members:
        group_members[chat_id] = set()

    # Track member
    group_members[chat_id].add(author)

    group_buffers[chat_id].append({
        "author": author,
        "text": text,
        "msg_id": msg.message_id,
        "ts": datetime.now().strftime("%H:%M")
    })
    if len(group_buffers[chat_id]) > 200:
        group_buffers[chat_id] = group_buffers[chat_id][-200:]

    # Check for @mention
    bot_username = (await context.bot.get_me()).username
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                mention = text[entity.offset:entity.offset + entity.length]
                if mention.lower() == f"@{bot_username.lower()}":
                    query = text.replace(mention, "").strip()
                    await handle_group_mention(update, context, query)
                    return

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Track members joining/being added to the group."""
    chat_id = update.effective_chat.id
    if chat_id not in group_members:
        group_members[chat_id] = set()
    member = update.chat_member.new_chat_member
    if member and member.status in ("member", "administrator", "creator"):
        name = member.user.full_name
        if name:
            group_members[chat_id].add(name)

# ─── RUN ──────────────────────────────────────────────────
if __name__ == "__main__":
    load_group_state()
    app = ApplicationBuilder().token(TOKEN).build()
    # Track members joining
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))
    # Group messages — must come before private catch-all
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
        handle_group
    ))
    # Private messages
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.COMMAND), handle))
    app.job_queue.run_repeating(autosave, interval=1800, first=1800)
    app.job_queue.run_repeating(scan_group_chat, interval=3600, first=60)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
