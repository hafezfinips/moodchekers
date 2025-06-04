import logging
import os
import json
import asyncio
import threading
import time
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from telegram.error import TimedOut, NetworkError

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "admin1234")
ADMIN_MAIN_ID = 7066529596

DATA_FOLDER = "userdata"
THOUGHTS_FOLDER = "thoughts"
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(THOUGHTS_FOLDER, exist_ok=True)

TIME_SLOTS = ["صبح", "ظهر", "عصر", "شب", "قبل خواب"]
TIME_REMINDERS = {"صبح": 8, "ظهر": 13, "عصر": 17, "شب": 21, "قبل خواب": 23}
reply_keyboard = [["وضعیت هفته", "وضعیت ماه", "🧠 خالی کردن ذهن", "📓 هیستوری ذهن"]]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

TYPING_THOUGHT = 1
WAITING_FOR_PASSWORD = 2
TYPING_BROADCAST = 3
TYPING_EXPORT_ID = 4
TYPING_SUMMARY_ID = 5
TYPING_PRIVATE_IDS = 6
TYPING_PRIVATE_MESSAGE = 7
TYPING_FILL_BACK = 8

ADMIN_PANEL = set()
user_states = {}
broadcast_targets = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    filepath = os.path.join(DATA_FOLDER, f"{user_id}.json")
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"joined": datetime.now().isoformat(), "moods": {}}, f)
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        joined = datetime.fromisoformat(data.get("joined"))
        now = datetime.now()
        missing_days = (now.date() - joined.date()).days + 1
        for i in range(missing_days):
            day = (now - timedelta(days=i)).date().isoformat()
            if day not in data["moods"]:
                data["moods"][day] = {}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f)
    await update.message.reply_text("سلام! منتظر نوتیف در ساعت‌های مشخص باش و در آن زمان نمره‌ات را وارد کن.", reply_markup=markup)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_MAIN_ID:
        ADMIN_PANEL.add(update.effective_user.id)
        await show_admin_menu(update)
    else:
        user_states[update.effective_user.id] = WAITING_FOR_PASSWORD
        await update.message.reply_text("🔐 لطفاً رمز پنل ادمین را وارد کنید:")

async def show_admin_menu(update: Update):
    keyboard = [["📄 لیست کاربران", "📢 پیام همگانی"], ["🗒 خلاصه کاربر", "🗂 خروجی کاربر"], ["🧠 ذهن کاربر", "🕒 زمان عضویت"], ["❌ خروج از پنل"], ["✉️ پیام خصوصی"]]
    await update.message.reply_text("🏧 پنل ادمین فعال شد.", reply_markup=ReplyKeyboardMarkup(keyboard + reply_keyboard, resize_keyboard=True))

async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user_id_str = str(user_id)
    username = update.effective_user.first_name or "کاربر"
    now = datetime.now()

    if user_states.get(user_id) == WAITING_FOR_PASSWORD:
        if text == ADMIN_PASSWORD:
            await context.bot.send_message(ADMIN_MAIN_ID, f"🗓 درخواست دسترسی از {user_id} دریافت شد.\n/allow {user_id}")
            await update.message.reply_text("⏳ درخواست شما برای ادمین ارسال شد.")
        else:
            await update.message.reply_text("❌ رمز اشتباه است.")
        user_states.pop(user_id)
        return

    if user_id in ADMIN_PANEL:
        state = user_states.get(user_id)
        if text == "🕒 زمان عضویت":
            users = os.listdir(DATA_FOLDER)
            msg = []
            for file in users:
                with open(os.path.join(DATA_FOLDER, file), "r", encoding="utf-8") as f:
                    d = json.load(f)
                    uid = file.replace(".json", "")
                    join_time = d.get("joined", "نامشخص")
                    msg.append(f"{uid}: {join_time}")
            await update.message.reply_text("\n".join(msg))
            return
        elif text == "🧠 ذهن کاربر":
            user_states[user_id] = TYPING_EXPORT_ID
            await update.message.reply_text("آیدی کاربر مورد نظر؟")
            return
        elif state == TYPING_EXPORT_ID:
            thoughts_file = os.path.join(THOUGHTS_FOLDER, f"{text}.txt")
            if os.path.exists(thoughts_file):
                with open(thoughts_file, "r", encoding="utf-8") as f:
                    await update.message.reply_text(f.read() or "(خالی)")
            else:
                await update.message.reply_text("❌ چیزی ثبت نشده.")
            user_states.pop(user_id)
            return

    if text == "📓 هیستوری ذهن":
        thoughts_file = os.path.join(THOUGHTS_FOLDER, f"{user_id_str}.txt")
        if os.path.exists(thoughts_file):
            with open(thoughts_file, "r", encoding="utf-8") as f:
                await update.message.reply_text(f.read() or "(خالی)")
        else:
            await update.message.reply_text("❌ هیچی ننوشتی هنوز.")
        return

    if text == "🧠 خالی کردن ذهن":
        user_states[user_id] = TYPING_THOUGHT
        await update.message.reply_text("📝 بنویس هرچی تو ذهنت هست:")
        return

    if user_states.get(user_id) == TYPING_THOUGHT:
        user_states.pop(user_id)
        filepath = os.path.join(THOUGHTS_FOLDER, f"{user_id_str}.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"[{now}] {text}\n")
        await update.message.reply_text(f"خیلی خوبه {username}، خوشحالم که ذهنت رو خالی کردی 💚 هر وقت دوباره خواستی، من همینجام.")
        return

    await update.message.reply_text("⏳ لطفاً فقط از گزینه‌های کیبورد استفاده کن یا حالتت رو وارد کن.")

def restart_bot():
    logging.warning("⏱ در حال ری‌استارت ربات پس از خطای Timeout...")
    time.sleep(5)
    sys.exit(1)

def run_dummy_server():
    class DummyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running.")
    server = HTTPServer(("0.0.0.0", 10000), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server).start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            app = ApplicationBuilder().token(TOKEN).read_timeout(10).connect_timeout(10).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("admin", admin))
            app.add_handler(CommandHandler("allow", lambda u, c: None))  # placeholder
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))
            app.run_polling()
        except (TimedOut, NetworkError) as e:
            logging.error(f"❌ خطا در اتصال: {e}")
            restart_bot()
            continue
        except Exception as e:
            logging.exception(f"🚨 خطای ناشناخته: {e}")
            time.sleep(5)
            continue
