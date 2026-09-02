import os
import sys
import re
import glob
import json
import logging
import time
import urllib.request
import urllib.parse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, date
import anthropic
import openai
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import MIND_BOT_TOKEN as TOKEN, ANTHROPIC_API_KEY, OWNER_ID, BRAIN_DIR, OPENAI_API_KEY

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
GROUP_STATE_FILE    = os.path.join(BRAIN_DIR, "chats/.state.json")
GROUP_SESSIONS_FILE = os.path.join(BRAIN_DIR, "chats/.sessions.json")
GROUP_BUFFERS_FILE  = os.path.join(BRAIN_DIR, "chats/.buffers.json")

# ─── CLIENT ───────────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
oai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
logging.basicConfig(level=logging.INFO)

# stores last digest text per user for voice playback
last_digest: dict[int, str] = {}

# Keywords that trigger auto-browse even without /browse mode
BROWSE_TRIGGERS = [
    "поищи", "погугли", "найди в сети", "найди в интернете",
    "что сейчас", "что происходит", "последние новости", "свежие новости",
    "актуальные новости", "новости про", "новости о",
    "search for", "look up", "find online", "latest news", "current news",
    "what's happening", "what is happening",
]

# Cached bot username — populated in post_init, avoids API call on every group message
_bot_username: str = ""

# ─── FORMATTING ───────────────────────────────────────────
HTML_FORMAT_INSTRUCTION = (
    "Format your reply using Telegram HTML: "
    "<b>bold</b>, <i>italic</i>, <code>code</code>, <blockquote>quote</blockquote>. "
    "Use plain text for everything else — no markdown asterisks or backticks."
)

def md_to_tg_html(text):
    """Convert basic markdown to Telegram HTML as fallback for responses that ignore the instruction."""
    # Escape any existing HTML special chars first (except our own tags)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text, flags=re.DOTALL)
    # Italic: *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<i>\1</i>', text)
    # Inline code: `text`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # Blockquote: > line
    text = re.sub(r'(?m)^&gt;\s?(.*)', r'<blockquote>\1</blockquote>', text)
    return text

async def send_html(target, text, **kwargs):
    """Send message with HTML parse mode, falling back to plain text on error."""
    try:
        if hasattr(target, 'edit_text'):
            return await target.edit_text(text, parse_mode=ParseMode.HTML, **kwargs)
        else:
            return await target.reply_text(text, parse_mode=ParseMode.HTML, **kwargs)
    except Exception:
        plain = re.sub(r'<[^>]+>', '', text)
        if hasattr(target, 'edit_text'):
            return await target.edit_text(plain, **kwargs)
        else:
            return await target.reply_text(plain, **kwargs)

# ─── SESSION STATE ────────────────────────────────────────
sessions = {}
session_saved_length = {}
user_think_mode = {}   # user_id -> bool
user_browse_mode = {}  # user_id -> bool
user_local_mode = {}   # user_id -> bool

# ─── OLLAMA (local GPU) ───────────────────────────────────
OLLAMA_HOST  = ""  # set in config.py
OLLAMA_PORT  = 11434
OLLAMA_MODEL = "gemma4:12b"
WINDOWS_MAC  = ""   # set in config.py

def ollama_alive() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/tags", timeout=3
        ) as r:
            return r.status == 200
    except Exception:
        return False

def wake_windows():
    try:
        import wakeonlan
        wakeonlan.send_magic_packet(WINDOWS_MAC)
        logging.info("WoL magic packet sent")
    except Exception as e:
        logging.warning(f"WoL failed: {e}")

async def ensure_ollama_awake() -> bool:
    if ollama_alive():
        return True
    wake_windows()
    import asyncio
    for _ in range(18):
        await asyncio.sleep(5)
        if ollama_alive():
            return True
    return False

def ask_ollama(messages: list[dict]) -> str:
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat"
    payload = json.dumps({"model": OLLAMA_MODEL, "messages": messages, "stream": False, "keep_alive": -1}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())["message"]["content"]

def ask_ollama_browse(messages: list[dict], max_steps: int = 6) -> str:
    """Agentic browse loop using Ollama tool calling."""
    tools = [
        {"type": "function", "function": {
            "name": "search",
            "description": "Search the web for current information. Use multiple focused queries for best results.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Search query"}
            }, "required": ["query"]}
        }},
        {"type": "function", "function": {
            "name": "fetch_page",
            "description": "Read the full content of a webpage by URL.",
            "parameters": {"type": "object", "properties": {
                "url": {"type": "string", "description": "URL to fetch"}
            }, "required": ["url"]}
        }}
    ]
    conv = list(messages)
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat"
    for step in range(max_steps):
        payload = json.dumps({
            "model": OLLAMA_MODEL, "messages": conv,
            "tools": tools, "stream": False, "keep_alive": -1
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        msg = resp["message"]
        conv.append(msg)
        if not msg.get("tool_calls"):
            return msg.get("content", "")
        for tc in msg["tool_calls"]:
            fn = tc["function"]["name"]
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            if fn == "search":
                results = _ddg_search(args.get("query", ""))
                tool_result = "\n".join(f"{r['url']}: {r['snippet']}" for r in results[:5]) or "No results"
            elif fn == "fetch_page":
                tool_result = _fetch_page(args.get("url", "")) or "Could not fetch page"
            else:
                tool_result = "Unknown tool"
            logging.info(f"ollama tool: {fn}({args}) → {len(tool_result)} chars")
            conv.append({"role": "tool", "content": tool_result})
    return conv[-1].get("content", "")

# ─── GROUP STATE ──────────────────────────────────────────
group_buffers = {}   # chat_id → [{"author", "text", "msg_id", "ts"}]
group_state = {}     # chat_id → {"name": str, "last_processed_id": int}
group_members = {}   # chat_id → set of known member names
group_sessions = {}   # chat_id → [{"role", "content"}] — conversation with bot
group_think = {}      # chat_id → bool
group_browse = {}     # chat_id → bool
group_local = {}      # chat_id → bool

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

def load_group_sessions():
    global group_sessions
    if os.path.exists(GROUP_SESSIONS_FILE):
        with open(GROUP_SESSIONS_FILE) as f:
            group_sessions = {int(k): v for k, v in json.load(f).items()}

def save_group_sessions():
    os.makedirs(os.path.dirname(GROUP_SESSIONS_FILE), exist_ok=True)
    with open(GROUP_SESSIONS_FILE, "w") as f:
        json.dump({str(k): v for k, v in group_sessions.items()}, f)

def load_group_buffers():
    global group_buffers
    if os.path.exists(GROUP_BUFFERS_FILE):
        with open(GROUP_BUFFERS_FILE) as f:
            group_buffers = {int(k): v for k, v in json.load(f).items()}

def save_group_buffers():
    os.makedirs(os.path.dirname(GROUP_BUFFERS_FILE), exist_ok=True)
    # Keep only last 50 messages per chat to avoid bloat
    trimmed = {str(k): v[-50:] for k, v in group_buffers.items()}
    with open(GROUP_BUFFERS_FILE, "w") as f:
        json.dump(trimmed, f)

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
        for root, dirs, files in os.walk(WIKI_DIR):
            dirs[:] = [d for d in sorted(dirs) if not d.startswith('.')]
            for fname in sorted(files):
                if fname.endswith(".md") and fname not in ("_index.md", ".gitkeep") and not fname.startswith('.'):
                    rel = os.path.relpath(os.path.join(root, fname), WIKI_DIR)
                    entries.append((rel, os.path.join(root, fname)))
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

    def make_snippet(path):
        with open(path, "r") as f:
            content = f.read()
        headers = [l.strip() for l in content.split("\n") if l.startswith("## ")]
        if headers:
            if len(headers) <= 8:
                return " | ".join(headers)
            # For long append-only logs: show date range + sample entries
            import re
            dates = [m.group(1) for h in headers for m in [re.search(r'(\d{4}-\d{2}-\d{2})', h)] if m]
            date_range = f"[{dates[0]} → {dates[-1]}, {len(headers)} entries]" if dates else f"[{len(headers)} entries]"
            return f"{date_range} {headers[0]} | ... | {headers[-1]}"
        return content[:200].replace("\n", " ")

    now = datetime.now()

    def age_tag(path):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            days = (now - mtime).days
            if days <= 3:
                return "🟢 updated <3d ago"
            elif days <= 14:
                return f"🟡 updated {days}d ago"
            else:
                return f"⚪ last updated {days}d ago"
        except Exception:
            return ""

    subdir_lines = []
    project_lines = []
    for label, path in entries:
        tag = age_tag(path)
        snippet = make_snippet(path)
        line = f"**{label}** [{tag}] — {snippet}"
        if label.startswith("projects/"):
            project_lines.append(line)
        elif "/" in label:  # wiki subdirectory files not covered by _index.md
            subdir_lines.append(line)

    index_text = wiki_index
    if subdir_lines:
        index_text += "\n\n### Wiki subfolders\n" + "\n".join(subdir_lines)
    if project_lines:
        index_text += "\n\n### Project files (sorted by recency)\n" + "\n".join(project_lines)

    return index_text, entries_dict, all_labels

def select_relevant_files(query, index_text, all_labels):
    """Pass 1: ask Haiku which files are relevant to the query."""
    if not index_text:
        return []
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system="""You are a search assistant. Given a user query and a file index, return ONLY the filenames (comma-separated) of files most likely to contain what the user is looking for. Return at most 5 files. If none are relevant, return NONE.

CRITICAL RULES:
- The index has a "⭐ CURRENT FOCUS" section — always check this first for current project context.
- Project files tagged "🟢 updated <3d ago" or "🟡 updated Xd ago" are recent and active. Prefer them.
- Project files tagged "⚪ last updated Xd ago" with large X (>30 days) are likely archived/completed — avoid unless directly asked.
- Files marked "(archived)" or "(completed)" in the description are OLD — never pick them for current status/signals.
- When the query asks about "signals", "what's going on", "current state", "recent updates" — ONLY pick files updated recently or from the CURRENT FOCUS section.

Think about intent, not just keywords. Examples:
- "what did we discuss on the standup" → look for chat logs, meeting notes, project status files
- "запись звонка / what was said on the call" → look for transcripts, call summaries, chat logs
- "статус проекта / current signals / сигналы" → CURRENT FOCUS file first, then recently updated files
- "кто такой X" → look for people files, mentions in project notes

Match files by what they likely *contain*, not just whether the query words appear in the filename.""",
        messages=[{"role": "user", "content": f"Today's date: {date.today()}\n\nQuery: {query}\n\nIndex:\n{index_text}"}]
    )
    result = response.content[0].text.strip()
    logging.info(f"Pass1 query={query[:80]!r} → {result[:200]}")
    if result == "NONE":
        return []
    selected = [f.strip() for f in result.split(",")]
    valid = set(all_labels)
    found = [f for f in selected if f in valid]
    logging.info(f"Pass1 valid files: {found}")
    return found

# ─── RAG ──────────────────────────────────────────────────
import numpy as np

_rag_index = []   # list of {label, text, embedding}
_rag_mtimes = {}  # path → mtime at index time

def _chunk_file(label, path):
    """Split a markdown file into section chunks."""
    with open(path, "r") as f:
        content = f.read()
    chunks = []
    current_header = ""
    current_lines = []
    for line in content.split("\n"):
        if line.startswith("## "):
            if current_lines:
                text = (current_header + "\n" + "\n".join(current_lines)).strip()
                if text:
                    chunks.append({"label": label, "text": text[:3000]})
            current_header = line
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        text = (current_header + "\n" + "\n".join(current_lines)).strip()
        if text:
            chunks.append({"label": label, "text": text[:3000]})
    # fallback: no sections → whole file as one chunk
    if not chunks:
        chunks.append({"label": label, "text": content[:3000]})
    return chunks

def _embed(texts, retries=5):
    """Embed a list of texts, return numpy array (n, dims)."""
    for attempt in range(retries):
        try:
            resp = oai_client.embeddings.create(model="text-embedding-3-small", input=texts)
            return np.array([d.embedding for d in resp.data], dtype="float32")
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt + 2
                logging.warning(f"Embedding error (attempt {attempt+1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

def build_rag_index():
    """Build or refresh the in-memory RAG index — delta mode: only re-embed changed files."""
    global _rag_index, _rag_mtimes
    try:
        _, entries_dict, _ = load_wiki_index()

        # Compute new mtimes and find what changed
        new_mtimes = {path: os.path.getmtime(path) for path in entries_dict.values()}
        changed = [(label, path) for label, path in entries_dict.items()
                   if new_mtimes[path] != _rag_mtimes.get(path)]

        if not changed and _rag_index:
            logging.info(f"RAG index up to date: {len(_rag_index)} chunks, 0 files changed")
            return

        # Keep chunks from files that still exist and haven't changed
        kept = [c for c in _rag_index
                if c["label"] in entries_dict
                and new_mtimes.get(entries_dict[c["label"]]) == _rag_mtimes.get(entries_dict[c["label"]])]

        # Build and embed chunks for changed/new files only
        new_chunks = []
        for label, path in changed:
            for c in _chunk_file(label, path):
                if c["text"].strip():
                    new_chunks.append({"label": c["label"], "text": c["text"]})

        if new_chunks:
            texts = [c["text"] for c in new_chunks]
            all_embeddings = []
            for i in range(0, len(texts), 50):
                all_embeddings.append(_embed(texts[i:i+50]))
                if i + 50 < len(texts):
                    time.sleep(1)
            embeddings = np.concatenate(all_embeddings, axis=0)
            for i, c in enumerate(new_chunks):
                c["embedding"] = embeddings[i]

        _rag_index = kept + new_chunks
        _rag_mtimes = new_mtimes
        logging.info(f"RAG index: {len(_rag_index)} chunks total | "
                     f"{len(changed)} files re-embedded | {len(kept)} chunks kept")
    except Exception as e:
        logging.error(f"RAG index build failed: {e}. Bot will start without index.")

def rag_search(query, top_k=6):
    """Return top_k relevant chunks for the query."""
    if not _rag_index:
        return ""
    q_emb = _embed([query])[0]
    scores = []
    for c in _rag_index:
        score = float(np.dot(q_emb, c["embedding"]) /
                      (np.linalg.norm(q_emb) * np.linalg.norm(c["embedding"]) + 1e-9))
        scores.append((score, c))
    scores.sort(key=lambda x: -x[0])
    top = scores[:top_k]
    parts = [f"### {c['label']}\n{c['text']}" for _, c in top]
    logging.info(f"RAG top files: {[c['label'] for _, c in top]}")
    return "\n\n".join(parts)

def load_wiki(query=None):
    if not query:
        return rag_search("general overview", top_k=10)
    return rag_search(query)

def _ddg_search(query: str) -> list:
    """Search DuckDuckGo via ddgs library, return list of {url, snippet}."""
    try:
        from ddgs import DDGS
        raw = DDGS().text(query, max_results=5)
        results = [{"url": r["href"], "snippet": r.get("body", "")} for r in (raw or [])]
        logging.info(f"DDG search '{query}': {len(results)} results")
        return results
    except Exception as e:
        logging.warning(f"DDG search failed: {e}")
        return []

def _fetch_page(url: str, max_chars: int = 2500) -> str:
    """Fetch a URL and return extracted text."""
    try:
        from newspaper import Article
        a = Article(url)
        a.download()
        a.parse()
        if a.text and len(a.text) > 100:
            return a.text[:max_chars]
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="ignore")[:80000]
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""

async def web_search(question: str) -> str:
    """Multi-query search: generate queries → search DDG → fetch pages."""
    import asyncio
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": f"Write 2-3 distinct search queries to research this. Return ONLY the queries, one per line, no numbering:\n\n{question}"}]
        )
        queries = [q.strip() for q in resp.content[0].text.strip().split("\n") if q.strip()][:3]
    except Exception:
        queries = [question]
    logging.info(f"browse queries: {queries}")
    all_results, seen = [], set()
    for q in queries:
        for r in _ddg_search(q):
            if r["url"] not in seen:
                seen.add(r["url"])
                all_results.append(r)
    if not all_results:
        return ""
    top = all_results[:4]
    texts = await asyncio.gather(*[asyncio.to_thread(_fetch_page, r["url"]) for r in top])
    parts = []
    for r, text in zip(top, texts):
        content = text or r["snippet"]
        if content:
            parts.append(f"Source: {r['url']}\n{content}")
    return "\n\n---\n\n".join(parts)

async def send_voice_digest(query, text):
    """Generate TTS and send as voice message(s), max 4096 chars per chunk."""
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    await query.answer()
    for chunk in chunks:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        try:
            response = oai_client.audio.speech.create(
                model="tts-1",
                voice="onyx",
                input=chunk
            )
            response.stream_to_file(tmp_path)
            with open(tmp_path, "rb") as audio:
                await query.message.reply_voice(voice=audio)
        finally:
            os.unlink(tmp_path)

def get_latest_digest(pattern="thinking"):
    if not os.path.exists(INSIGHTS_DIR):
        return None
    files = sorted(glob.glob(os.path.join(INSIGHTS_DIR, f"*{pattern}*.md")))
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

async def scheduled_reindex(context):
    build_rag_index()

def mode_status(uid):
    t = "ON" if user_think_mode.get(uid) else "OFF"
    b = "ON" if user_browse_mode.get(uid) else "OFF"
    l = "ON" if user_local_mode.get(uid) else "OFF"
    return f"🧠 think: {t}  🌐 browse: {b}  🖥 local: {l}"

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
    if text.startswith("/") and text not in ["/think", "/browse", "/digest", "/status", "/tasks", "/local"]:
        return

    # Digest — latest thinking digest (owner only)
    if text.lower() in ["дайджест", "/digest"] and not is_guest:
        content = get_latest_digest("thinking")
        if not content:
            await msg.reply_text("Thinking digest пока нет")
            return
        last_digest[user_id] = content
        chunks = split_digest(content)
        for chunk in chunks[:-1]:
            await msg.reply_text(chunk)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔊 Слушать", callback_data=f"voice_digest:{user_id}")]])
        await msg.reply_text(chunks[-1], reply_markup=keyboard)
        return

    # Status — latest weekly planning digest (owner only)
    if text.lower() == "/status" and not is_guest:
        content = get_latest_digest("weekly-digest")
        if not content:
            await msg.reply_text("Дайджест пока нет")
            return
        last_digest[user_id] = content
        chunks = split_digest(content)
        for chunk in chunks[:-1]:
            await msg.reply_text(chunk)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔊 Слушать", callback_data=f"voice_digest:{user_id}")]])
        await msg.reply_text(chunks[-1], reply_markup=keyboard)
        return

    # Toggle local mode (owner only)
    if text == "/local" and not is_guest:
        if not OLLAMA_HOST:
            await msg.reply_text("⚠️ Ollama не настроен. Добавь OLLAMA_HOST в config.py.")
            return
        user_local_mode[user_id] = not user_local_mode.get(user_id, False)
        await msg.reply_text(mode_status(user_id))
        return

    # Toggle think mode (owner only)
    if text == "/think" and not is_guest:
        user_think_mode[user_id] = not user_think_mode.get(user_id, False)
        await msg.reply_text(mode_status(user_id))
        return

    # Toggle browse mode (owner only)
    if text == "/browse" and not is_guest:
        user_browse_mode[user_id] = not user_browse_mode.get(user_id, False)
        await msg.reply_text(mode_status(user_id))
        return

    # End session
    if text == "??":
        if not is_guest:
            if user_id in sessions and sessions[user_id]:
                save_session(user_id, sessions[user_id], False)
                sessions.pop(user_id)
                session_saved_length.pop(user_id, None)
                await msg.reply_text("✓ saved to brain")
            else:
                await msg.reply_text("No active session")
            return
        else:
            if user_id in sessions and sessions[user_id]:
                save_session(user_id, sessions[user_id], True)
                sessions.pop(user_id)
                session_saved_length.pop(user_id, None)
            return

    if user_id not in sessions:
        sessions[user_id] = []

    sessions[user_id].append({"role": "user", "content": text})

    thinking_msg = await msg.reply_text("…")

    user_model = load_user_model(public=is_guest)
    wiki_context = load_wiki(query=text)

    think_mode = user_think_mode.get(user_id, False) and not is_guest
    local_mode = user_local_mode.get(user_id, False) and not is_guest

    text_lower = text.lower()
    auto_browse = any(t in text_lower for t in BROWSE_TRIGGERS)
    browse_mode = (user_browse_mode.get(user_id, False) or auto_browse) and not is_guest

    web_context = ""
    if browse_mode:
        web_context = await web_search(text)

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
- Always reply in the same language as the guest's message. {HTML_FORMAT_INSTRUCTION}
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
                "text": f"USER MODEL:\n{user_model[:3000]}{web_extra}\n\nYour role is NOT to answer questions — it is to expand thinking. For each message:\n- Connect the idea to unexpected angles, broader concepts, or contrasting perspectives\n- Ask one sharp question that might shift how Misha sees the problem\n- Surface what might be missing or worth questioning\n- Think out loud, be speculative, bring in ideas from outside his world\n\nBe a sparring partner, not a search engine. Challenge gently. Surprise occasionally. Always reply in the same language as the user's message. " + HTML_FORMAT_INSTRUCTION
            }
        ]
    else:
        system_blocks = [
            {
                "type": "text",
                "text": f"You are Misha's thinking partner — sharp, curious, a little unpredictable.\n\nYou know everything he knows:\n\n{wiki_context}",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"USER MODEL — who Misha is:\n{user_model[:3000]}{web_extra}\n\nHow to talk with him:\n- Match response length to the message: a quick remark gets a quick reply, a deep question gets a full answer. Never pad, never truncate.\n- Be direct, skip preamble. No \"Great question!\", no summaries of what you just said.\n- Have opinions. Agree or push back, don't sit on the fence.\n- If something in his notes connects to what he's saying — bring it in naturally, don't announce it.\n- Match his energy: if he's thinking out loud, think with him. If he wants a quick answer, give it.\n- Always reply in the same language as his message."
            }
        ]

    if local_mode:
        if not await ensure_ollama_awake():
            await thinking_msg.edit_text("🖥 Большой комп выключен. Включи его или отключи /local.")
            return
        system_text = "\n\n".join(b["text"] for b in system_blocks if b.get("type") == "text")
        system_text = system_text.replace(
            "WEB SEARCH: returned no results — do not claim to be browsing.", ""
        )
        system_text += "\n\nYou have access to search and fetch_page tools. Use them whenever the user asks about news, current events, or anything that may have changed recently. Search proactively — do not say you cannot access the internet."
        ollama_messages = [{"role": "system", "content": system_text}] + sessions[user_id]
        try:
            import asyncio
            reply = await asyncio.to_thread(ask_ollama_browse, ollama_messages)
        except Exception as e:
            await thinking_msg.edit_text(f"🖥 Ollama не отвечает: {e}")
            return
        reply = md_to_tg_html(reply)
    else:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            system=system_blocks,
            messages=sessions[user_id]
        )
        reply = response.content[0].text
        u = response.usage
        logging.info(f"tokens: input={u.input_tokens} cache_read={getattr(u, 'cache_read_input_tokens', 0)} cache_write={getattr(u, 'cache_creation_input_tokens', 0)} output={u.output_tokens}")

    sessions[user_id].append({"role": "assistant", "content": reply})
    await send_html(thinking_msg, reply)

# ─── GROUP CHAT ───────────────────────────────────────────
async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Reply to @mention in group using wiki + public user model + recent chat history."""
    thinking = await update.message.reply_text("…")
    chat_id = update.effective_chat.id

    # Pass 1 uses only the user's query — not chat history or bot responses
    session_text = " ".join(m["content"] for m in group_sessions.get(chat_id, [])[-20:])
    wiki_query = query or session_text[:200]
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
        await thinking.edit_text(f"🧠 think: {'ON' if group_think[chat_id] else 'OFF'}  🌐 browse: {'ON' if group_browse.get(chat_id) else 'OFF'}  🖥 local: {'ON' if group_local.get(chat_id) else 'OFF'}")
        return
    if query.strip() == "/browse":
        group_browse[chat_id] = not group_browse.get(chat_id, False)
        await thinking.edit_text(f"🧠 think: {'ON' if group_think.get(chat_id) else 'OFF'}  🌐 browse: {'ON' if group_browse[chat_id] else 'OFF'}  🖥 local: {'ON' if group_local.get(chat_id) else 'OFF'}")
        return
    if query.strip() == "/local":
        if not OLLAMA_HOST:
            await thinking.edit_text("⚠️ Ollama не настроен.")
            return
        group_local[chat_id] = not group_local.get(chat_id, False)
        await thinking.edit_text(f"🧠 think: {'ON' if group_think.get(chat_id) else 'OFF'}  🌐 browse: {'ON' if group_browse.get(chat_id) else 'OFF'}  🖥 local: {'ON' if group_local[chat_id] else 'OFF'}")
        return

    # Detect language from query (which has the @mention stripped)
    # Fall back to chat history if query has no Cyrillic (e.g. empty or slash command)
    sample = (query or "")[:200] or chat_history[:200]
    lang_instruction = "Reply in Russian." if any(
        'Ѐ' <= c <= 'ӿ' for c in sample
    ) else "Reply in the same language as the user's message."
    lang_instruction += f" {HTML_FORMAT_INSTRUCTION}"

    query_lower = (query or "").lower()
    auto_browse_group = any(t in query_lower for t in BROWSE_TRIGGERS)
    do_browse = group_browse.get(chat_id) or auto_browse_group
    web_context = ""
    if do_browse:
        web_context = await web_search(query or chat_history[:100])
    if web_context:
        web_section = f"\n\nWEB SEARCH RESULTS:\n{web_context}"
    elif do_browse:
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

    # Always include recent chat context so bot sees what's happening around the mention
    if chat_history:
        user_content = f"Recent chat:\n{chat_history}\n\n{query or 'What do you think?'}"
    else:
        user_content = query or "What do you think?"

    group_sessions[chat_id].append({"role": "user", "content": user_content})
    # Keep last 20 exchanges
    if len(group_sessions[chat_id]) > 40:
        group_sessions[chat_id] = group_sessions[chat_id][-40:]

    if group_local.get(chat_id):
        if not await ensure_ollama_awake():
            await thinking.edit_text("🖥 Большой комп выключен.")
            return
        try:
            ollama_messages = [{"role": "system", "content": system}] + group_sessions[chat_id]
            reply = ask_ollama(ollama_messages)
            reply = md_to_tg_html(reply)
        except Exception as e:
            await thinking.edit_text(f"🖥 Ollama не отвечает: {e}")
            return
    else:
        model = "claude-sonnet-4-6" if group_think.get(chat_id) else "claude-haiku-4-5-20251001"
        response = client.messages.create(
            model=model,
            max_tokens=800,
            system=system,
            messages=group_sessions[chat_id]
        )
        reply = response.content[0].text
    group_sessions[chat_id].append({"role": "assistant", "content": reply})
    save_group_sessions()
    await send_html(thinking, reply)

EPISODE_GAP_HOURS = 4  # gap between messages that marks episode boundary

def split_into_episodes(messages, gap_hours=EPISODE_GAP_HOURS):
    """Split message list into episodes by time gap. Returns list of episode lists.
    An episode is considered closed only if a gap has occurred after it."""
    if not messages:
        return []
    episodes = []
    current = [messages[0]]
    for msg in messages[1:]:
        prev_ts = current[-1].get("unix_ts", 0)
        curr_ts = msg.get("unix_ts", 0)
        if prev_ts and curr_ts and (curr_ts - prev_ts) > gap_hours * 3600:
            episodes.append(current)
            current = [msg]
        else:
            current.append(msg)
    # current episode is open (ongoing) — don't process it yet
    return episodes

async def scan_group_chat(context):
    """Hourly job: save closed episodes as transcripts to /raw for Cowork to process."""
    archive_dir = os.path.join(BRAIN_DIR, "archive")
    for chat_id, messages in list(group_buffers.items()):
        if not messages:
            continue
        if chat_id not in group_state:
            group_state[chat_id] = {"name": str(chat_id), "title": str(chat_id), "last_processed_id": 0}
        state = group_state[chat_id]
        last_id = state["last_processed_id"]
        new_messages = [m for m in messages if m["msg_id"] > last_id]
        if not new_messages:
            continue

        chat_name = state["name"]
        chat_title = state.get("title", chat_name)

        closed_episodes = split_into_episodes(new_messages)
        if not closed_episodes:
            continue

        last_processed_id = last_id
        for episode in closed_episodes:
            episode_ts = episode[-1].get("unix_ts", 0)
            timestamp = datetime.fromtimestamp(episode_ts).strftime("%Y%m%d_%H%M%S") if episode_ts else datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = os.path.join(RAW_DIR, f"{timestamp}_chat_{chat_name}.md")
            # Skip if already saved to raw or archive
            archive_path = os.path.join(archive_dir, f"{timestamp}_chat_{chat_name}.md")
            if os.path.exists(fpath) or os.path.exists(archive_path):
                logging.info(f"scan_group_chat [{chat_name}]: skipping {timestamp} (already exists)")
                last_processed_id = episode[-1]["msg_id"]
                continue
            transcript = "\n".join(f"[{m.get('ts','')}] {m['author']}: {m['text']}" for m in episode)
            content = (
                f"category: conversation\n"
                f"source: group_chat\n"
                f"chat: {chat_title}\n"
                f"date: {timestamp}\n\n"
                f"{transcript}"
            )
            with open(fpath, "w") as f:
                f.write(content)
            last_processed_id = episode[-1]["msg_id"]
            logging.info(f"scan_group_chat [{chat_name}]: saved episode {timestamp} ({len(episode)} msgs)")

        group_state[chat_id]["last_processed_id"] = last_processed_id
        save_group_state()

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
            group_state[chat_id] = {"name": chat_name, "title": chat_title, "last_processed_id": 0}
    if chat_id not in group_members:
        group_members[chat_id] = set()

    # Track member
    group_members[chat_id].add(author)

    group_buffers[chat_id].append({
        "author": author,
        "text": text,
        "msg_id": msg.message_id,
        "ts": datetime.now().strftime("%H:%M"),
        "unix_ts": msg.date.timestamp() if msg.date else 0,
    })
    if len(group_buffers[chat_id]) > 200:
        group_buffers[chat_id] = group_buffers[chat_id][-200:]
    save_group_buffers()

    # Check for @mention
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                mention = text[entity.offset:entity.offset + entity.length]
                if mention.lower() == f"@{_bot_username.lower()}":
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
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    if query.data.startswith("voice_digest:"):
        uid = int(query.data.split(":")[1])
        if uid != query.from_user.id:
            await query.answer("Не твой дайджест")
            return
        text = last_digest.get(uid)
        if not text:
            await query.answer("Дайджест не найден")
            return
        await query.answer("Генерирую аудио…")
        await send_voice_digest(query, text)

async def post_init(app):
    global _bot_username
    me = await app.bot.get_me()
    _bot_username = me.username
    from telegram import BotCommand
    await app.bot.set_my_commands([
        BotCommand("think",   "Режим глубокого анализа (Sonnet)"),
        BotCommand("browse",  "Поиск в интернете"),
        BotCommand("digest",  "Последний thinking digest"),
        BotCommand("status",  "Статус проектов за неделю"),
        BotCommand("tasks",   "Открытые задачи в Notion"),
    ])

if __name__ == "__main__":
    load_group_state()
    load_group_sessions()
    load_group_buffers()
    build_rag_index()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    # Track members joining
    from telegram.ext import ChatMemberHandler
    app.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))
    # Group messages — must come before private catch-all
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
        handle_group
    ))
    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))
    # Private messages
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.COMMAND), handle))
    app.job_queue.run_repeating(autosave, interval=1800, first=1800)
    app.job_queue.run_repeating(scan_group_chat, interval=3600, first=60)
    app.job_queue.run_repeating(scheduled_reindex, interval=43200, first=3600)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
