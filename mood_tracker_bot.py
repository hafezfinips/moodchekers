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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not os.path.exists(os.path.join(DATA_FOLDER, f"{user_id}.json")):
        with open(os.path.join(DATA_FOLDER, f"{user_id}.json"), "w", encoding="utf-8") as f:
            json.dump({"joined": datetime.now().isoformat(), "moods": {}}, f)
    if update.effective_user.id in ADMIN_PANEL:
        await show_admin_menu(update)
    else:
        await update.message.reply_text("سلام! منتظر نوتیف در ساعت‌های مشخص باش و در آن زمان نمره‌ات را وارد کن.", reply_markup=markup)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_MAIN_ID:
        ADMIN_PANEL.add(update.effective_user.id)
        await show_admin_menu(update)
    else:
        user_states[update.effective_user.id] = WAITING_FOR_PASSWORD
        await update.message.reply_text("🔐 لطفاً رمز پنل ادمین را وارد کنید:")

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id) == WAITING_FOR_PASSWORD:
        if update.message.text == ADMIN_PASSWORD:
            await context.bot.send_message(ADMIN_MAIN_ID, f"📥 درخواست دسترسی از {user_id} دریافت شد.\n/allow {user_id}")
            await update.message.reply_text("⏳ درخواست شما برای ادمین ارسال شد.")
        else:
            await update.message.reply_text("❌ رمز اشتباه است.")
        user_states.pop(user_id)

async def allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_MAIN_ID:
        return
    try:
        uid = int(context.args[0])
        ADMIN_PANEL.add(uid)
        await context.bot.send_message(uid, "✅ دسترسی شما تأیید شد.")
    except:
        await update.message.reply_text("❗️ دستور نادرست. استفاده صحیح:\n/allow user_id")

async def show_admin_menu(update: Update):
    keyboard = [["📄 لیست کاربران", "📢 پیام همگانی"], ["🧾 خلاصه کاربر", "🗂 خروجی کاربر"], ["❌ خروج از پنل"]]
    await update.message.reply_text("🎛 پنل ادمین فعال شد.", reply_markup=ReplyKeyboardMarkup(keyboard + reply_keyboard, resize_keyboard=True))

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if user_id not in ADMIN_PANEL:
        return
    if text == "📄 لیست کاربران":
        users = os.listdir(DATA_FOLDER)
        await update.message.reply_text(f"👥 تعداد کاربران: {len(users)}\n" + "\n".join(users))
    elif text == "📢 پیام همگانی":
        user_states[user_id] = TYPING_BROADCAST
        await update.message.reply_text("📨 پیام خود را وارد کنید تا برای همه کاربران ارسال شود.")
    elif text == "🗂 خروجی کاربر":
        user_states[user_id] = TYPING_EXPORT_ID
        await update.message.reply_text("🔍 لطفاً آیدی کاربر موردنظر را وارد کنید:")
    elif text == "🧾 خلاصه کاربر":
        user_states[user_id] = TYPING_SUMMARY_ID
        await update.message.reply_text("🔎 لطفاً آیدی کاربر را برای خلاصه آماری وارد کنید:")
    elif text == "❌ خروج از پنل":
        ADMIN_PANEL.remove(user_id)
        await update.message.reply_text("🛑 از حالت ادمین خارج شدید.", reply_markup=markup)

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    text = update.message.text
    if state == TYPING_BROADCAST:
        del user_states[user_id]
        for uid in os.listdir(DATA_FOLDER):
            await context.bot.send_message(int(uid), f"📢 پیام از ادمین:\n{text}")
        await update.message.reply_text("✅ پیام برای همه ارسال شد.")
    elif state == TYPING_EXPORT_ID:
        del user_states[user_id]
        file_path = os.path.join(DATA_FOLDER, f"{text}.json")
        if not os.path.exists(file_path):
            await update.message.reply_text("❌ کاربری با این آیدی یافت نشد.")
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        messages = []
        for date, times in data.get("moods", {}).items():
            msg = f"📅 {date}: " + ", ".join([f"{k}={v}" for k, v in times.items()])
            messages.append(msg)
        await update.message.reply_text("\n".join(messages) or "❗️ دیتایی ثبت نشده.")
    elif state == TYPING_SUMMARY_ID:
        del user_states[user_id]
        file_path = os.path.join(DATA_FOLDER, f"{text}.json")
        if not os.path.exists(file_path):
            await update.message.reply_text("❌ کاربری با این آیدی یافت نشد.")
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        all_scores = []
        for day in data["moods"].values():
            all_scores.extend([int(s) for s in day.values()])
        avg = sum(all_scores)/len(all_scores) if all_scores else 0
        await update.message.reply_text(f"📊 میانگین نمره: {avg:.2f}\nروزهای فعال: {len(data['moods'])}\nآخرین روز: {max(data['moods']) if data['moods'] else '---'}")

# بقیه توابع از قبل در فایل هستند
# حالا راه‌اندازی اپلیکیشن

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
