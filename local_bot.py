import asyncio
import json
import logging
import os
import time
import urllib.request
from datetime import datetime

from duckduckgo_search import DDGS
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from config import LOCAL_BOT_TOKEN as TOKEN, OWNER_ID, BRAIN_DIR

logging.basicConfig(level=logging.INFO)

OLLAMA_HOST  = ""  # set in config.py
OLLAMA_PORT  = 11434
OLLAMA_MODEL = "gemma4:12b"
RAW_DIR      = os.path.join(BRAIN_DIR, "raw")

BROWSE_TRIGGERS = [
    "поищи", "погугли", "найди в сети", "найди в интернете",
    "что сейчас", "что происходит", "последние новости", "свежие новости",
    "актуальные новости", "новости про", "новости о",
    "search for", "look up", "find online", "latest news", "current news",
    "what's happening", "what is happening",
]


def ddg_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddg:
            results = list(ddg.text(query, max_results=max_results))
        if not results:
            return ""
        return "\n".join(f"{r['href']}: {r['body']}" for r in results)
    except Exception as e:
        logging.warning(f"DDG search failed: {e}")
        return ""

sessions: dict[int, list] = {}


def ollama_chat(messages: list) -> str:
    url = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat"
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": -1,
        "options": {"num_ctx": 8192},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())["message"]["content"]


def save_session(user_id: int, messages: list) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    content = f"---\ntags: [local-chat]\ndate: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n"
    for m in messages:
        role = "Misha" if m["role"] == "user" else "Ollama"
        content += f"**{role}:** {m['content']}\n\n"
    path = os.path.join(RAW_DIR, f"{timestamp}_local_chat.md")
    with open(path, "w") as f:
        f.write(content)
    logging.info(f"saved session → {path}")


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    # Save and clear session
    if text == "??":
        msgs = sessions.pop(user_id, [])
        if msgs:
            save_session(user_id, msgs)
            await update.message.reply_text("✓ saved")
        else:
            await update.message.reply_text("No active session")
        return

    if user_id not in sessions:
        sessions[user_id] = []

    # Auto web search on browse triggers
    text_lower = text.lower()
    web_snippet = ""
    if any(t in text_lower for t in BROWSE_TRIGGERS):
        web_snippet = await asyncio.to_thread(ddg_search, text)

    if web_snippet:
        user_content = f"{text}\n\nWEB SEARCH RESULTS:\n{web_snippet}"
    else:
        user_content = text
    sessions[user_id].append({"role": "user", "content": user_content})

    thinking = await update.message.reply_text("…")
    start = time.time()

    async def tick():
        while True:
            await asyncio.sleep(5)
            elapsed = int(time.time() - start)
            try:
                await thinking.edit_text(f"… {elapsed}с")
            except Exception:
                pass

    tick_task = asyncio.create_task(tick())
    try:
        reply = await asyncio.to_thread(ollama_chat, sessions[user_id])
    except Exception as e:
        tick_task.cancel()
        await thinking.edit_text(f"🖥 Ollama недоступна: {e}")
        sessions[user_id].pop()
        return
    finally:
        tick_task.cancel()

    sessions[user_id].append({"role": "assistant", "content": reply})
    if len(reply) <= 4096:
        await thinking.edit_text(reply)
    else:
        await thinking.delete()
        for i in range(0, len(reply), 4096):
            await update.message.reply_text(reply[i:i + 4096])


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    sessions.pop(user_id, None)
    await update.message.reply_text("✓ cleared")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(
        f"🖥 {OLLAMA_MODEL}\n\n"
        "Просто пиши — отвечу через Ollama.\n"
        "?? — сохранить сессию и начать заново\n"
        "/clear — очистить без сохранения"
    )


async def post_init(app) -> None:
    await app.bot.set_my_commands([
        BotCommand("start", "Показать статус"),
        BotCommand("clear", "Очистить сессию без сохранения"),
    ])


if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle))
    app.run_polling()
