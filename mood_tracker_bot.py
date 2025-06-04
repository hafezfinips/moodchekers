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
    ContextTypes, filters
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
shown_admin_notice = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not os.path.exists(os.path.join(DATA_FOLDER, f"{user_id}.json")):
        with open(os.path.join(DATA_FOLDER, f"{user_id}.json"), "w", encoding="utf-8") as f:
            json.dump({"joined": datetime.now().isoformat(), "moods": {}}, f)

    if update.effective_user.id in ADMIN_PANEL:
        if update.effective_user.id not in shown_admin_notice:
            await update.message.reply_text("🎛 پنل ادمین فعال شد.", reply_markup=ReplyKeyboardMarkup(
                [["📄 لیست کاربران", "📢 پیام همگانی"], ["🧾 خلاصه کاربر", "🗂 خروجی کاربر"], ["❌ خروج از پنل"]] + reply_keyboard,
                resize_keyboard=True))
            shown_admin_notice.add(update.effective_user.id)
        else:
            await update.message.reply_text("🤖 ربات آماده دریافت اطلاعات است.", reply_markup=markup)
    else:
        await update.message.reply_text("سلام! منتظر نوتیف در ساعت‌های مشخص باش و در آن زمان نمره‌ات را وارد کن.", reply_markup=markup)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_MAIN_ID:
        ADMIN_PANEL.add(update.effective_user.id)
        await update.message.reply_text("🎛 پنل ادمین فعال شد.", reply_markup=ReplyKeyboardMarkup(
            [["📄 لیست کاربران", "📢 پیام همگانی"], ["🧾 خلاصه کاربر", "🗂 خروجی کاربر"], ["❌ خروج از پنل"]] + reply_keyboard,
            resize_keyboard=True))
        shown_admin_notice.add(update.effective_user.id)
    else:
        user_states[update.effective_user.id] = WAITING_FOR_PASSWORD
        await update.message.reply_text("🔐 لطفاً رمز پنل ادمین را وارد کنید:")

async def allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_MAIN_ID:
        return
    try:
        uid = int(context.args[0])
        ADMIN_PANEL.add(uid)
        await context.bot.send_message(uid, "✅ دسترسی شما تأیید شد.")
    except:
        await update.message.reply_text("❗️ دستور نادرست. استفاده صحیح:\n/allow user_id")

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = user_states.get(user_id)

    if state == WAITING_FOR_PASSWORD:
        if text == ADMIN_PASSWORD:
            await context.bot.send_message(ADMIN_MAIN_ID, f"📥 درخواست دسترسی از {user_id} دریافت شد.\n/allow {user_id}")
            await update.message.reply_text("⏳ درخواست شما برای ادمین ارسال شد.")
        else:
            await update.message.reply_text("❌ رمز اشتباه است.")
        user_states.pop(user_id)
        return

    if user_id in ADMIN_PANEL:
        if text == "📄 لیست کاربران":
            users = os.listdir(DATA_FOLDER)
            await update.message.reply_text(f"👥 تعداد کاربران: {len(users)}\n" + "\n".join(users))
        elif text == "📢 پیام همگانی":
            user_states[user_id] = TYPING_BROADCAST
            await update.message.reply_text("📨 پیام خود را وارد کنید تا برای همه ارسال شود.")
        elif text == "🗂 خروجی کاربر":
            user_states[user_id] = TYPING_EXPORT_ID
            await update.message.reply_text("🔍 آیدی کاربر؟")
        elif text == "🧾 خلاصه کاربر":
            user_states[user_id] = TYPING_SUMMARY_ID
            await update.message.reply_text("🔎 آیدی برای خلاصه آماری؟")
        elif text == "❌ خروج از پنل":
            ADMIN_PANEL.remove(user_id)
            shown_admin_notice.discard(user_id)
            await update.message.reply_text("🛑 از حالت ادمین خارج شدید.", reply_markup=markup)
        elif state == TYPING_BROADCAST:
            user_states.pop(user_id)
            for uid in os.listdir(DATA_FOLDER):
                await context.bot.send_message(int(uid), f"📢 پیام ادمین:\n{text}")
            await update.message.reply_text("✅ پیام ارسال شد.")
        elif state == TYPING_EXPORT_ID:
            user_states.pop(user_id)
            file_path = os.path.join(DATA_FOLDER, f"{text}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                messages = [f"📅 {date}: {', '.join([f'{k}={v}' for k, v in mood.items()])}" for date, mood in data.get("moods", {}).items()]
                await update.message.reply_text("\n".join(messages) or "❗️ دیتایی نیست.")
            else:
                await update.message.reply_text("❌ کاربر پیدا نشد.")
        elif state == TYPING_SUMMARY_ID:
            user_states.pop(user_id)
            file_path = os.path.join(DATA_FOLDER, f"{text}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                all_scores = [int(v) for day in data["moods"].values() for v in day.values()]
                avg = sum(all_scores)/len(all_scores) if all_scores else 0
                await update.message.reply_text(f"📊 میانگین نمره: {avg:.2f}\nروزهای فعال: {len(data['moods'])}\nآخرین روز: {max(data['moods']) if data['moods'] else '---'}")
            else:
                await update.message.reply_text("❌ کاربر پیدا نشد.")
        else:
            await update.message.reply_text("لطفاً از دکمه‌ها استفاده کنید.")
        return

    # حالت‌های کاربر عادی
    if text == "🧠 خالی کردن ذهن":
        user_states[user_id] = TYPING_THOUGHT
        await update.message.reply_text("📝 بنویس هرچی تو ذهنت هست:")
    elif user_states.get(user_id) == TYPING_THOUGHT:
        user_states.pop(user_id)
        filepath = os.path.join(THOUGHTS_FOLDER, f"{user_id}.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] {text}\n")
        await update.message.reply_text("✅ ذخیره شد. هر وقت خواستی باز هم بنویس.")
    else:
        await update.message.reply_text("⏳ لطفاً از گزینه‌های کیبورد استفاده کن یا حالتت رو وارد کن.")

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    app.run_polling()
