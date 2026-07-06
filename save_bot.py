import os
import re
import sys
import json
import base64
import logging
import urllib.request
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from datetime import datetime
from openai import OpenAI
import anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import BRAIN_BOT_TOKEN as TOKEN, OPENAI_API_KEY, ANTHROPIC_API_KEY, OWNER_ID, BRAIN_DIR
from config import NOTION_TOKEN, NOTION_DB

# ─── CONFIG ───────────────────────────────────────────────
ALLOWED_USER = OWNER_ID
RAW_DIR      = os.path.join(BRAIN_DIR, "raw")

CATEGORIES = ["idea", "thought", "case", "link", "cool", "question", "todo", "reference", "event"]

# ─── CLIENTS ──────────────────────────────────────────────
openai_client = OpenAI(api_key=OPENAI_API_KEY)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
logging.basicConfig(level=logging.INFO)

# ─── BATCH STATE ──────────────────────────────────────────
batch_buffer = []
batch_count = 0
batch_task = None
last_chat_id = None
last_bot = None
last_tasks_list = []  # cache for /done N command
media_group_buffer = {}   # group_id -> {"file_ids": [], "author": str|None, "caption": str}
media_group_tasks = {}    # group_id -> asyncio.Task

# ─── HELPERS ──────────────────────────────────────────────
def extract_url(text):
    pattern = r'https?://[^\s]+'
    urls = re.findall(pattern, text or "")
    return urls[0] if urls else None

def summarize_youtube(title, transcript):
    """Summarize YouTube transcript via Claude Haiku. Returns summary string."""
    try:
        prompt = f"""Video: {title}

Transcript:
{transcript}

Write a tight summary — max 5 bullet points, each 1-2 sentences.
Extract the actual substance: if there's a list, name the items; if there's a how-to, give the core steps; if there's an argument, state the conclusion.
Skip hype, intros, outros, and anything meta about the video itself.
Reply in English if the transcript is in English, in Russian if the transcript is in Russian, otherwise in English."""
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logging.warning(f"summarize_youtube failed: {e}")
        return None

def get_youtube_transcript(url):
    """Fetch YouTube subtitles via yt-dlp. Returns (title, transcript_text) or (title, None)."""
    import tempfile, subprocess, shutil
    tmpdir = tempfile.mkdtemp()
    try:
        title_result = subprocess.run(
            ["/home/pi/.local/bin/yt-dlp", "--skip-download", "--print", "title", url],
            capture_output=True, text=True
        )
        title = title_result.stdout.strip().splitlines()[0] if title_result.stdout.strip() else ""

        subprocess.run([
            "/home/pi/.local/bin/yt-dlp", "--skip-download",
            "--write-auto-sub", "--write-sub",
            "--sub-lang", "en,ru",
            "--sub-format", "vtt",
            "-o", os.path.join(tmpdir, "sub"),
            url
        ], capture_output=True, text=True)

        vtt_files = [f for f in os.listdir(tmpdir) if ".vtt" in f]
        if not vtt_files:
            return title, None

        with open(os.path.join(tmpdir, vtt_files[0]), encoding="utf-8") as f:
            raw = f.read()

        # Parse incremental VTT blocks: take last text line per block, dedup adjacent
        lines = []
        for block in raw.strip().split("\n\n"):
            block_lines = block.strip().splitlines()
            text_lines = [l for l in block_lines
                          if l and "-->" not in l
                          and not l.startswith("WEBVTT")
                          and not l.startswith("Kind:")
                          and not l.startswith("Language:")]
            if text_lines:
                clean = re.sub(r"<[^>]+>", "", text_lines[-1]).strip()
                if clean:
                    lines.append(clean)
        deduped = [lines[0]] if lines else []
        for l in lines[1:]:
            if l != deduped[-1]:
                deduped.append(l)
        return title, " ".join(deduped)
    except Exception as e:
        logging.warning(f"get_youtube_transcript failed: {e}")
        return "", None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def scrape_url(url):
    is_youtube = "youtube.com" in url or "youtu.be" in url
    if is_youtube:
        title, transcript = get_youtube_transcript(url)
        if transcript:
            return title, transcript
        # Fallback: description only
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
            title = info.get("title", "")
            desc = info.get("description", "") or ""
            channel = info.get("channel", "") or info.get("uploader", "")
            return title, f"Channel: {channel}\n\n{desc[:5000]}"
        except Exception as e:
            logging.warning(f"yt-dlp metadata failed for {url}: {e}")
            return None, None
    # Web pages: markitdown first, newspaper3k fallback
    try:
        from markitdown import MarkItDown
        result = MarkItDown().convert(url)
        if result.text_content and len(result.text_content) > 200:
            return result.title or "", result.text_content[:30000]
    except Exception as e:
        logging.debug(f"markitdown scrape failed for {url}: {e}")
    try:
        from newspaper import Article
        article = Article(url)
        article.download()
        article.parse()
        return article.title, article.text
    except:
        return None, None

def transcribe(file_path):
    try:
        with open(file_path, "rb") as f:
            result = openai_client.audio.transcriptions.create(model="whisper-1", file=f)
        return result.text
    except:
        return None

def detect_category(text, is_forward=False):
    """Use Claude Haiku to detect category from free-form text."""
    try:
        forward_hint = "This is a FORWARDED message — the user saved it as a reminder or task for themselves. If it contains a request, action, or something the user needs to do — categorize as todo.\n\n" if is_forward else ""
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": f"""Categorize this note. Reply with exactly one word from this list:
idea, thought, case, link, cool, question, todo, reference, event

Categories:
idea — concepts, options, proposals, directions for a project; creative input; things to consider or try ("варианты:", "что если", "идеи для")
thought — personal observation, reflection, or opinion; something the author is working through
todo — a concrete action the author must do; has a clear executor and verb ("надо", "нужно", "не забыть", "позвонить", "купить")
case — an example, case study, or execution worth noting
link — a URL or reference to external content
cool — something inspiring, interesting, or worth saving without a specific category
question — an open question or something the author wants to explore
reference — factual information, data, a definition, or something to look up later
event — a specific time-bound happening: meeting, birthday, deadline, appointment

{forward_hint}Note: {text[:300]}

Reply with one word only:"""
            }]
        )
        category = response.content[0].text.strip().lower()
        logging.info(f"detect_category: input={text[:80]!r} → raw={response.content[0].text!r} → result={category!r}")
        if category in CATEGORIES:
            return category
        return "thought"
    except Exception as e:
        logging.warning(f"detect_category failed: {e}")
        return "thought"

# ─── NOTION ───────────────────────────────────────────────
def parse_todo(text):
    """Use Haiku to extract tasks from text. Returns a list of task dicts."""
    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().year
    try:
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": f"""Extract tasks from this text. If there are multiple dates or actions — create a separate task for each. Reply with a JSON array only, no explanation.

Today is {today}.

Each task object:
- "title": clean task name, remove filler words like "нужно", "надо", "не забыть", "напомни мне", "туду". Short and action-oriented. Keep the same language as the input.
- "deadline": ISO date (YYYY-MM-DD) if mentioned, or null. Resolve "сегодня"→{today}, "завтра"→tomorrow, "17 июля"→{year}-07-17 etc.
- "priority": "🔴 Urgent" if very urgent, "🟡 High" if important, "⚪ Normal" for regular tasks, null if not clear.

Text: {text}

Reply with JSON array only:"""}]
        )
        raw = response.content[0].text.strip()
        # Extract JSON array or object even if Haiku wrapped it in text
        match = re.search(r'(\[.*\]|\{.*\})', raw, re.DOTALL)
        if not match:
            raise ValueError(f"no JSON found in: {raw}")
        result = json.loads(match.group(1))
        logging.info(f"parse_todo result: {result}")
        return result if isinstance(result, list) else [result]
    except Exception as e:
        logging.warning(f"parse_todo failed: {e}")
        return [{"title": text[:100], "deadline": None, "priority": None}]

def write_sync_flag(filepath, flag):
    """Insert 'flag: synced' into front matter of an existing .md file."""
    try:
        with open(filepath, "r") as f:
            content = f.read()
        # Find end of front matter (first blank line)
        lines = content.split("\n")
        insert_at = None
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == "":
                insert_at = i
                break
        if insert_at is None:
            insert_at = len(lines)
        lines.insert(insert_at, f"{flag}: synced")
        with open(filepath, "w") as f:
            f.write("\n".join(lines))
    except Exception as e:
        logging.warning(f"write_sync_flag failed: {e}")

def add_notion_task(title, deadline=None, priority=None, source=None):
    """Add a task to Notion database."""
    try:
        props = {
            "Name": {"title": [{"text": {"content": title}}]},
        }
        if deadline:
            props["Due Date"] = {"date": {"start": deadline}}
        if priority:
            props["Priority"] = {"select": {"name": priority}}
        if source:
            props["Source"] = {"select": {"name": source}}

        data = json.dumps({"parent": {"database_id": NOTION_DB}, "properties": props}).encode()
        req = urllib.request.Request(
            "https://api.notion.com/v1/pages",
            data=data,
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read().decode())
            logging.info(f"notion task added: {title}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logging.warning(f"add_notion_task failed: {e.code} {body}")
        return False
    except Exception as e:
        logging.warning(f"add_notion_task failed: {e}")
        return False

# ─── NOTION READ ──────────────────────────────────────────
def get_notion_tasks():
    """Return open tasks from Notion, grouped by status. Updates last_tasks_list."""
    global last_tasks_list
    try:
        data = json.dumps({
            "filter": {"property": "Status", "status": {"does_not_equal": "Done"}},
            "sorts": [{"property": "Status", "direction": "ascending"}]
        }).encode()
        req = urllib.request.Request(
            f"https://api.notion.com/v1/databases/{NOTION_DB}/query",
            data=data,
            headers={"Authorization": f"Bearer {NOTION_TOKEN}",
                     "Content-Type": "application/json",
                     "Notion-Version": "2022-06-28"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read().decode()).get("results", [])
        tasks = []
        for page in results:
            props = page["properties"]
            title = props["Name"]["title"]
            name = title[0]["text"]["content"] if title else "(no title)"
            status = props.get("Status", {}).get("status", {}).get("name", "")
            due = (props.get("Due Date", {}).get("date") or {}).get("start", "")
            tasks.append({"id": page["id"], "name": name, "status": status, "due": due})
        last_tasks_list = tasks
        return tasks
    except Exception as e:
        logging.warning(f"get_notion_tasks failed: {e}")
        return []

def mark_notion_done(page_id):
    """Set task status to Done in Notion."""
    try:
        data = json.dumps({"properties": {"Status": {"status": {"name": "Done"}}}}).encode()
        req = urllib.request.Request(
            f"https://api.notion.com/v1/pages/{page_id}",
            data=data,
            headers={"Authorization": f"Bearer {NOTION_TOKEN}",
                     "Content-Type": "application/json",
                     "Notion-Version": "2022-06-28"},
            method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return True
    except Exception as e:
        logging.warning(f"mark_notion_done failed: {e}")
        return False

def scan_for_hidden_todos(text, source, fpath=None):
    """Scan text for explicit action items and add them to Notion."""
    if not text or len(text) < 10:
        return
    try:
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": f"""Scan this text for clear, explicit action items only.
NOT vague intentions like "хорошо бы попробовать" or "интересно было бы".
ONLY concrete actions like "позвонить Васе", "купить молоко", "отправить файл".

If found, return JSON array: [{{"title": "...", "deadline": null}}]
If nothing found, return: []

Text: {text[:1000]}

Reply with JSON only:"""}]
        )
        raw = response.content[0].text.strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not match:
            return
        items = json.loads(match.group(0))
        synced = False
        for item in items:
            if item.get("title"):
                if add_notion_task(item["title"], item.get("deadline"), None, source):
                    synced = True
                logging.info(f"scan_for_hidden_todos: found '{item['title']}'")
        if synced and fpath:
            write_sync_flag(fpath, "notion")
    except Exception as e:
        logging.warning(f"scan_for_hidden_todos failed: {e}")


# ─── MEDIA GROUP ──────────────────────────────────────────
async def ocr_photo_file(file_id, bot):
    """Download photo by file_id and OCR it. Returns text or None."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    jpg_path = os.path.join(RAW_DIR, f"{ts}_tmp.jpg")
    try:
        tg_file = await bot.get_file(file_id)
        await tg_file.download_to_drive(jpg_path)
        with open(jpg_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        ocr = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                {"type": "text", "text": "Extract all text from this image verbatim. If it contains event details (date, time, location, names) — note them clearly. Reply with extracted text only."}
            ]}]
        )
        text = ocr.content[0].text.strip()
        return text if len(text) > 10 else None
    except Exception as e:
        logging.warning(f"ocr_photo_file failed: {e}")
        return None
    finally:
        if os.path.exists(jpg_path):
            os.remove(jpg_path)

async def flush_media_group(group_id):
    await asyncio.sleep(2)
    info = media_group_buffer.pop(group_id, None)
    media_group_tasks.pop(group_id, None)
    if not info or not last_bot:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    texts = [t for t in [await ocr_photo_file(fid, last_bot) for fid in info["file_ids"]] if t]
    combined = "\n\n---\n\n".join(texts)
    author = info.get("author")
    count = len(info["file_ids"])

    if author:
        parts = [f"source: telegram_forward\nauthor: {author}\ndate: {timestamp}\n\nnot my thought - forwarded album:"]
        if info.get("caption"):
            parts.append(f"caption: {info['caption']}")
        if combined:
            parts.append(f"extracted text:\n{combined}")
        content = "\n\n".join(parts)
        category = "cool"
        if combined:
            scan_for_hidden_todos(combined, "text")
    else:
        if combined:
            category = detect_category(combined)
            content = f"category: {category}\nsource: photo_album\ndate: {timestamp}\nphotos: {count}\n\n{combined}"
            fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")
            if category == "todo":
                synced = any(
                    add_notion_task(todo["title"], todo.get("deadline"), todo.get("priority"), "text")
                    for todo in parse_todo(combined)
                )
                if synced:
                    write_sync_flag(fpath, "notion")
            else:
                scan_for_hidden_todos(combined, "text", fpath)
        else:
            category = "cool"
            content = f"category: {category}\nsource: photo_album\ndate: {timestamp}\nphotos: {count}\n\n(no text extracted)"
            fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")

    with open(fpath, "w") as f:
        f.write(content)
    label = f"album ({count})" if count > 1 else "photo"
    if last_chat_id:
        await last_bot.send_message(chat_id=last_chat_id, text=f"✓ {label} → {category}")


# ─── BATCH ────────────────────────────────────────────────
async def flush_batch():
    global batch_buffer, batch_count, batch_task, last_chat_id, last_bot
    if not batch_buffer:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined = "\n\n---\n\n".join(batch_buffer)

    # Determine category
    if "source: external_link" in combined:
        category = "link"
    elif "source: telegram_forward" in combined:
        category = "cool"
    elif "source: self_voice" in combined:
        category = "thought"
    else:
        category = "thought"

    content = f"category: {category}\ndate: {timestamp}\n\n{combined}"
    filename = f"{timestamp}_{category}.md"
    fpath = os.path.join(RAW_DIR, filename)
    with open(fpath, "w") as f:
        f.write(content)

    count = batch_count
    batch_buffer = []
    batch_count = 0
    batch_task = None

    if category == "todo":
        synced = any(
            add_notion_task(todo["title"], todo.get("deadline"), todo.get("priority"), "text")
            for todo in parse_todo(combined)
        )
        if synced:
            write_sync_flag(fpath, "notion")
    elif category == "link":
        scan_for_hidden_todos(combined, "text", fpath)

    if last_bot and last_chat_id:
        msg = f"✓ {category}" if count == 1 else f"✓ batch of {count} → {category}"
        await last_bot.send_message(chat_id=last_chat_id, text=msg)

async def schedule_flush():
    await asyncio.sleep(5)
    await flush_batch()

# ─── HANDLER ──────────────────────────────────────────────
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global batch_buffer, batch_count, batch_task, last_chat_id, last_bot

    if update.effective_user.id != ALLOWED_USER:
        return

    msg = update.message
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    last_chat_id = update.effective_chat.id
    last_bot = context.bot

    # Reply context
    reply_ctx = ""
    if msg.reply_to_message:
        r = msg.reply_to_message
        reply_author = r.from_user.full_name if r.from_user else "unknown"
        reply_text = (r.text or r.caption or "")[:300]
        reply_ctx = f"reply_to_author: {reply_author}\nreply_to_text: {reply_text}\n"

    if batch_task:
        batch_task.cancel()

    # Voice → transcribe immediately, save directly
    if msg.voice:
        await msg.reply_text("transcribing...")
        file = await context.bot.get_file(msg.voice.file_id)
        ogg_path = os.path.join(RAW_DIR, f"{timestamp}_voice.ogg")
        await file.download_to_drive(ogg_path)
        text = transcribe(ogg_path)
        if text:
            category = detect_category(text)
            fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")
            content = f"category: {category}\nsource: self_voice\ndate: {timestamp}\n\n{text}"
            with open(fpath, "w") as f:
                f.write(content)
            os.remove(ogg_path)
            if category == "todo":
                synced = any(
                    add_notion_task(todo["title"], todo.get("deadline"), todo.get("priority"), "voice")
                    for todo in parse_todo(text)
                )
                if synced:
                    write_sync_flag(fpath, "notion")
            await msg.reply_text(f"✓ {category}\n\n{text[:200]}")
        else:
            await msg.reply_text("✓ saved")
        return

    # Forward check BEFORE photo/document (fixes forwarded albums)
    if msg.forward_origin:
        forward_from = getattr(msg.forward_origin, 'sender_user', None)
        author = forward_from.full_name if forward_from else "unknown"
        forwarded_by = msg.from_user.full_name if msg.from_user else "unknown"

        if msg.photo:
            group_id = msg.media_group_id or f"fwd_{timestamp}"
            if group_id not in media_group_buffer:
                media_group_buffer[group_id] = {"file_ids": [], "author": author, "caption": msg.caption or ""}
            media_group_buffer[group_id]["file_ids"].append(msg.photo[-1].file_id)
            if group_id in media_group_tasks:
                media_group_tasks[group_id].cancel()
            media_group_tasks[group_id] = asyncio.create_task(flush_media_group(group_id))
            return

        if msg.document:
            orig_name = msg.document.file_name or "document"
            file = await context.bot.get_file(msg.document.file_id)
            file_path = os.path.join(RAW_DIR, f"{timestamp}_{orig_name}")
            await file.download_to_drive(file_path)
            try:
                from markitdown import MarkItDown
                result = MarkItDown().convert(file_path)
                if result.text_content and len(result.text_content) > 50:
                    archive_path = os.path.join(BRAIN_DIR, "archive", f"{timestamp}_{orig_name}")
                    os.rename(file_path, archive_path)
                    category = detect_category(result.text_content[:500], is_forward=True)
                    content = (
                        f"category: {category}\nsource: document\n"
                        f"original_author: {author}\nforwarded_by: {forwarded_by}\nfilename: {orig_name}\ndate: {timestamp}\n"
                        f"archive: {timestamp}_{orig_name}\n\n"
                        f"{result.text_content}"
                    )
                    doc_fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")
                    with open(doc_fpath, "w") as f:
                        f.write(content)
                    await msg.reply_text(f"✓ {category} (from {author}: {orig_name})")
                    return
            except Exception as e:
                logging.warning(f"markitdown failed on forwarded doc: {e}")
            await msg.reply_text("✓ file")
            return

        # Forwarded text/link
        url = extract_url(msg.text)
        content = f"source: telegram_forward\noriginal_author: {author}\nforwarded_by: {forwarded_by}\ndate: {timestamp}\n{reply_ctx}\nnot my thought - forwarded content:\n\n{msg.text or ''}"
        if url:
            is_yt = "youtube.com" in url or "youtu.be" in url
            title, text = scrape_url(url)
            if text:
                if is_yt:
                    summary = summarize_youtube(title, text)
                    if summary:
                        full = f"📹 {title}\n\n{summary}"
                        for i in range(0, len(full), 4000):
                            await context.bot.send_message(chat_id=last_chat_id, text=full[i:i+4000])
                    content += f"\n\n---\nurl: {url}\ntitle: {title}\n\n"
                    if summary:
                        content += f"## Summary\n{summary}\n\n## Transcript\n"
                    content += text
                else:
                    content += f"\n\n---\nurl: {url}\ntitle: {title}\n\n{text[:3000]}"
        scan_for_hidden_todos(msg.text or '', "text")
        batch_buffer.append(content)
        batch_count += 1

    # Photo (own) → album buffer or single OCR
    elif msg.photo:
        if msg.media_group_id:
            group_id = msg.media_group_id
            if group_id not in media_group_buffer:
                media_group_buffer[group_id] = {"file_ids": [], "author": None, "caption": msg.caption or ""}
            media_group_buffer[group_id]["file_ids"].append(msg.photo[-1].file_id)
            if group_id in media_group_tasks:
                media_group_tasks[group_id].cancel()
            media_group_tasks[group_id] = asyncio.create_task(flush_media_group(group_id))
            return
        # Single photo
        extracted = await ocr_photo_file(msg.photo[-1].file_id, context.bot)
        if extracted:
            category = detect_category(extracted)
            fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")
            content = f"category: {category}\nsource: photo\ndate: {timestamp}\n\n{extracted}"
            with open(fpath, "w") as f:
                f.write(content)
            if category == "todo":
                synced = any(
                    add_notion_task(todo["title"], todo.get("deadline"), todo.get("priority"), "text")
                    for todo in parse_todo(extracted)
                )
                if synced:
                    write_sync_flag(fpath, "notion")
            else:
                scan_for_hidden_todos(extracted, "text", fpath)
            await msg.reply_text(f"✓ {category}\n\n{extracted[:200]}")
        else:
            # No text — save jpg as-is
            file = await context.bot.get_file(msg.photo[-1].file_id)
            await file.download_to_drive(os.path.join(RAW_DIR, f"{timestamp}_photo.jpg"))
            await msg.reply_text("✓ photo")
        return

    # Document → markitdown + keep original in archive
    elif msg.document:
        orig_name = msg.document.file_name or "document"
        file = await context.bot.get_file(msg.document.file_id)
        file_path = os.path.join(RAW_DIR, f"{timestamp}_{orig_name}")
        await file.download_to_drive(file_path)
        converted = False
        try:
            from markitdown import MarkItDown
            result = MarkItDown().convert(file_path)
            if result.text_content and len(result.text_content) > 50:
                # Move original to archive, save markdown to raw
                archive_path = os.path.join(BRAIN_DIR, "archive", f"{timestamp}_{orig_name}")
                os.rename(file_path, archive_path)
                category = detect_category(result.text_content[:500])
                content = (
                    f"category: {category}\nsource: document\n"
                    f"filename: {orig_name}\ndate: {timestamp}\n"
                    f"archive: {timestamp}_{orig_name}\n\n"
                    f"{result.text_content}"
                )
                doc_fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")
                with open(doc_fpath, "w") as f:
                    f.write(content)
                scan_for_hidden_todos(result.text_content[:1000], "text", doc_fpath)
                await msg.reply_text(f"✓ {category} (converted from {orig_name})")
                converted = True
        except ImportError:
            pass
        except Exception as e:
            logging.warning(f"markitdown failed: {e}")
        if not converted:
            await msg.reply_text("✓ file")
        return

    # Text
    elif msg.text:
        url = extract_url(msg.text)
        if url:
            is_yt = "youtube.com" in url or "youtu.be" in url
            title, text = scrape_url(url)
            if is_yt and text:
                summary = summarize_youtube(title, text)
                if summary:
                    full = f"📹 {title}\n\n{summary}"
                    for i in range(0, len(full), 4000):
                        await msg.reply_text(full[i:i+4000])
                content = f"source: external_link\ndate: {timestamp}\nurl: {url}\ntitle: {title or ''}\n\n"
                if summary:
                    content += f"## Summary\n{summary}\n\n## Transcript\n"
                content += text
            else:
                content = f"source: external_link\ndate: {timestamp}\nurl: {url}\ntitle: {title or ''}\n\n{text[:10000] if text else msg.text}"
        else:
            category = detect_category(msg.text)
            content = f"category: {category}\nsource: self_text\ndate: {timestamp}\n{reply_ctx}\n{msg.text}"
            fpath = os.path.join(RAW_DIR, f"{timestamp}_{category}.md")
            with open(fpath, "w") as f:
                f.write(content)
            if category == "todo":
                synced = any(
                    add_notion_task(todo["title"], todo.get("deadline"), todo.get("priority"), "text")
                    for todo in parse_todo(msg.text)
                )
                if synced:
                    write_sync_flag(fpath, "notion")
            else:
                scan_for_hidden_todos(msg.text, "text", fpath)
            await msg.reply_text(f"✓ {category}")
            return

        batch_buffer.append(content)
        batch_count += 1

    else:
        return

    batch_task = asyncio.create_task(schedule_flush())

# ─── COMMANDS ─────────────────────────────────────────────
async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return
    tasks = get_notion_tasks()
    if not tasks:
        await update.message.reply_text("No open tasks")
        return
    groups = {}
    for t in tasks:
        groups.setdefault(t["status"], []).append(t)
    lines = []
    n = 1
    for status in ["Pending Review", "This Week", "Postponed", "Backlog"]:
        if status not in groups:
            continue
        lines.append(f"\n**{status}**")
        for t in groups[status]:
            due = f" [{t['due']}]" if t["due"] else ""
            lines.append(f"{n}. {t['name']}{due}")
            n += 1
    await update.message.reply_text("\n".join(lines))


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER:
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /done <number>")
        return
    n = int(context.args[0])
    if not last_tasks_list or n < 1 or n > len(last_tasks_list):
        await update.message.reply_text("Run /tasks first to get the list")
        return
    task = last_tasks_list[n - 1]
    if mark_notion_done(task["id"]):
        await update.message.reply_text(f"✓ done: {task['name']}")
    else:
        await update.message.reply_text("Failed to update Notion")


# ─── RUN ──────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(MessageHandler(filters.ALL, handle))
    app.run_polling()
