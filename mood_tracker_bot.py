import logging
import os
import json
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import matplotlib.pyplot as plt
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "admin1234")
ADMIN_MAIN_ID = 7066529596

DATA_FOLDER = "userdata"
THOUGHTS_FOLDER = "thoughts"
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(THOUGHTS_FOLDER, exist_ok=True)

TIME_SLOTS = ["صبح", "ظهر", "عصر", "شب", "قبل خواب"]
TIME_REMINDERS = {"صبح": 8, "ظهر": 13, "عصر": 17, "شب": 21, "قبل خواب": 23}
reply_keyboard = [["وضعیت هفته", "وضعیت ماه", "🧠 خالی کردن ذهن"]]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

TYPING_THOUGHT = 1
WAITING_FOR_PASSWORD = 2
TYPING_BROADCAST = 3
TYPING_EXPORT_ID = 4
TYPING_SUMMARY_ID = 5

ADMIN_PANEL = set()
user_states = {}

async def reminder_task(app):
    while True:
        now = datetime.now()
        for slot, hour in TIME_REMINDERS.items():
            if now.hour == hour and now.minute == 0:
                for user_id in os.listdir(DATA_FOLDER):
                    file_path = os.path.join(DATA_FOLDER, user_id)
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    today = datetime.now().strftime("%Y-%m-%d")
                    if today not in data["moods"] or slot not in data["moods"].get(today, {}):
                        await app.bot.send_message(int(user_id), f"⌛️ وقتشه حالت رو ثبت کنی - تایم: {slot}")
        await asyncio.sleep(60)

def save_mood(user_id, time_slot, score):
    file_path = os.path.join(DATA_FOLDER, f"{user_id}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in data["moods"]:
        data["moods"][today] = {}
    data["moods"][today][time_slot] = score
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_current_slot():
    hour = datetime.now().hour
    for slot, slot_hour in TIME_REMINDERS.items():
        if hour == slot_hour:
            return slot
    return None

def get_pending_slot(user_id):
    file_path = os.path.join(DATA_FOLDER, f"{user_id}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in data["moods"]:
        return None
    for slot in TIME_SLOTS:
        if TIME_REMINDERS[slot] < datetime.now().hour and slot not in data["moods"][today]:
            return slot
    return None

def check_enough_days(user_id, days_required):
    file_path = os.path.join(DATA_FOLDER, f"{user_id}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    mood_dates = list(data["moods"].keys())
    return len(mood_dates) >= days_required, days_required - len(mood_dates)

def generate_chart(user_id, title):
    file_path = os.path.join(DATA_FOLDER, f"{user_id}.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    moods = data["moods"]
    scores_by_day = []
    for date in sorted(moods.keys())[-14:]:
        entries = moods[date].values()
        avg = sum(int(s) for s in entries) / len(entries)
        scores_by_day.append((date, avg))
    if not scores_by_day:
        return None
    dates = [item[0] for item in scores_by_day]
    scores = [item[1] for item in scores_by_day]
    plt.style.use('ggplot')
    plt.figure(figsize=(10, 5))
    plt.plot(dates, scores, marker='o', linestyle='-', linewidth=2)
    plt.title(title, fontsize=16, fontweight='bold')
    plt.xlabel("Date", fontsize=12)
    plt.ylabel("Mood (1-10)", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.xticks(rotation=45)
    plt.tight_layout()
    filename = f"mood_chart_{user_id}.png"
    plt.savefig(filename)
    plt.close()
    return filename

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)
    now_slot = get_current_slot()

    if text in ["وضعیت هفته", "وضعیت ماه"]:
        required = 7 if "هفته" in text else 30
        enough, remaining = check_enough_days(user_id, required)
        if not enough:
            await update.message.reply_text(f"📊 برای دریافت گزارش باید {required} روز کامل ثبت داشته باشید. {remaining} روز دیگر باقی مانده.")
            return
        chart = generate_chart(user_id, text)
        if chart:
            await update.message.reply_photo(photo=open(chart, "rb"))

    elif text == "🧠 خالی کردن ذهن":
        user_states[update.effective_user.id] = TYPING_THOUGHT
        await update.message.reply_text("📝 بنویس هرچی تو ذهنته:")

    elif user_states.get(update.effective_user.id) == TYPING_THOUGHT:
        user_states.pop(update.effective_user.id)
        file_path = os.path.join(THOUGHTS_FOLDER, f"{user_id}.txt")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat()}] {text}")
        await update.message.reply_text("🧘‍♂️ ذخیره شد. سبک‌تر شدی؟")

    elif text.isdigit():
        pending_slot = get_pending_slot(user_id)
        if pending_slot and now_slot != pending_slot:
            await update.message.reply_text(f"❗️اول باید مود مربوط به '{pending_slot}' رو ثبت کنی.")
            return
        if now_slot:
            save_mood(user_id, now_slot, int(text))
            await update.message.reply_text("✅ ثبت شد! منتظر نوبت بعدی باش.")
        else:
            await update.message.reply_text("⏰ الان زمان ثبت مود نیست. لطفاً در ساعت تعیین‌شده پاسخ بده.")

    else:
        await update.message.reply_text("لطفاً فقط عدد بین 1 تا 10 یا گزینه‌های کیبورد رو ارسال کن.")

# سرور ساختگی برای جلوگیری از خاموشی در هاست

def run_dummy_server():
    class DummyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running.")

    server = HTTPServer(("0.0.0.0", 10000), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server).start()

# راه‌اندازی اپلیکیشن

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("allow", allow))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_commands))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    loop = asyncio.get_event_loop()
    loop.create_task(reminder_task(app))
    app.run_polling()
