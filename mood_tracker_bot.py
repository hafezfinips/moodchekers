import logging
import asyncio
import nest_asyncio
nest_asyncio.apply()
import os
import json
import asyncio
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
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
reply_keyboard = [["وضعیت هفته", "وضعیت ماه", "🧠 خالی کردن ذهن"]]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

TYPING_THOUGHT = 1
WAITING_FOR_PASSWORD = 2
TYPING_BROADCAST = 3
TYPING_EXPORT_ID = 4
TYPING_SUMMARY_ID = 5
TYPING_PRIVATE_IDS = 6
TYPING_PRIVATE_MESSAGE = 7

ADMIN_PANEL = set()
user_states = {}
broadcast_targets = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not os.path.exists(os.path.join(DATA_FOLDER, f"{user_id}.json")):
        with open(os.path.join(DATA_FOLDER, f"{user_id}.json"), "w", encoding="utf-8") as f:
            json.dump({"joined": datetime.now().isoformat(), "moods": {}}, f)
    await update.message.reply_text("سلام! منتظر نوتیف در ساعت‌های مشخص باش و در آن زمان نمره‌ات را وارد کن.", reply_markup=markup)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_MAIN_ID:
        ADMIN_PANEL.add(update.effective_user.id)
        await show_admin_menu(update)
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

async def show_admin_menu(update: Update):
    keyboard = [["📄 لیست کاربران", "📢 پیام همگانی"], ["🧾 خلاصه کاربر", "🗂 خروجی کاربر"], ["📬 پیام به کاربر", "❌ خروج از پنل"]]
    await update.message.reply_text("🎛 پنل ادمین فعال شد.", reply_markup=ReplyKeyboardMarkup(keyboard + reply_keyboard, resize_keyboard=True))

async def handle_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    username = update.effective_user.first_name or "کاربر"
    text = update.message.text
    now = datetime.now()

    if user_states.get(user_id) == WAITING_FOR_PASSWORD:
        if text == ADMIN_PASSWORD:
            await context.bot.send_message(ADMIN_MAIN_ID, f"📅 درخواست دسترسی از {user_id} دریافت شد.\n/allow {user_id}")
            await update.message.reply_text("⏳ درخواست شما برای ادمین ارسال شد.")
        else:
            await update.message.reply_text("❌ رمز اشتباه است.")
        user_states.pop(user_id)
        return

    if user_id in ADMIN_PANEL:
        state = user_states.get(user_id)
        if text == "📄 لیست کاربران":
            users = os.listdir(DATA_FOLDER)
            await update.message.reply_text(f"👥 تعداد کاربران: {len(users)}\n" + "\n".join(users))
            return
        elif text == "📢 پیام همگانی":
            user_states[user_id] = TYPING_BROADCAST
            await update.message.reply_text("📨 پیام خود را وارد کنید تا برای همه کاربران ارسال شود.")
            return
        elif text == "🗂 خروجی کاربر":
            user_states[user_id] = TYPING_EXPORT_ID
            await update.message.reply_text("🔍 لطفاً آیدی کاربر موردنظر را وارد کنید:")
            return
        elif text == "🧾 خلاصه کاربر":
            user_states[user_id] = TYPING_SUMMARY_ID
            await update.message.reply_text("🔎 لطفاً آیدی کاربر را برای خلاصه آماری وارد کنید:")
            return
        elif text == "📬 پیام به کاربر":
            user_states[user_id] = TYPING_PRIVATE_IDS
            await update.message.reply_text("👤 آیدی یا آیدی‌های کاربران را وارد کن (با کاما جدا کن):")
            return
        elif text == "❌ خروج از پنل":
            ADMIN_PANEL.remove(user_id)
            await update.message.reply_text("🛑 از حالت ادمین خارج شدید.", reply_markup=markup)
            return
        elif state == TYPING_BROADCAST:
            user_states.pop(user_id)
            success, fail = 0, 0
            for filename in os.listdir(DATA_FOLDER):
                if filename.endswith(".json") and filename.replace(".json", "").isdigit():
                    uid = int(filename.replace(".json", ""))
                    try:
                        await context.bot.send_message(uid, f"📢 پیام از ادمین:\n{text}")
                        success += 1
                    except:
                        fail += 1
            await update.message.reply_text(f"✅ پیام برای {success} نفر ارسال شد.\n❌ شکست‌خورده: {fail}")
            return
        elif state == TYPING_EXPORT_ID:
            user_states.pop(user_id)
            file_path = os.path.join(DATA_FOLDER, f"{text}.json")
            if not os.path.exists(file_path):
                await update.message.reply_text("❌ کاربری با این آیدی یافت نشد.")
                return
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = [f"📅 {d}: " + ", ".join([f"{k}={v}" for k, v in t.items()]) for d, t in data.get("moods", {}).items()]
            await update.message.reply_text("\n".join(messages) or "❗️ دیتایی ثبت نشده.")
            return
        elif state == TYPING_SUMMARY_ID:
            user_states.pop(user_id)
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
            return
        elif state == TYPING_PRIVATE_IDS:
            user_states[user_id] = (TYPING_PRIVATE_MESSAGE, text.split(","))
            await update.message.reply_text("📝 حالا متن پیامی که می‌خوای بفرستی رو بنویس:")
            return
        elif isinstance(state, tuple) and state[0] == TYPING_PRIVATE_MESSAGE:
            ids = [i.strip() for i in state[1]]
            user_states.pop(user_id)
            success = 0
            fail = 0
            for uid in ids:
                try:
                    await context.bot.send_message(int(uid), f"📬 پیام اختصاصی از ادمین:\n{text}")
                    success += 1
                except:
                    fail += 1
            await update.message.reply_text(f"✅ پیام برای {success} نفر ارسال شد.\n❌ شکست‌خورده: {fail}")
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

    if text in ["وضعیت هفته", "وضعیت ماه"]:
        file_path = os.path.join(DATA_FOLDER, f"{user_id_str}.json")
        if not os.path.exists(file_path):
            await update.message.reply_text("❗️ ابتدا با /start ثبت‌نام کن.")
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mood_dates = list(data.get("moods", {}).keys())
        required = 7 if "هفته" in text else 30
        if len(mood_dates) < required:
            await update.message.reply_text(f"📊 برای دریافت گزارش باید {required} روز ثبت‌نام داشته باشی. فقط {len(mood_dates)} روز داری.")
            return
        scores_by_day = []
        for date in sorted(data["moods"].keys())[-14:]:
            entries = data["moods"][date].values()
            avg = sum(int(s) for s in entries) / len(entries)
            scores_by_day.append((date, avg))
        dates = [x[0] for x in scores_by_day]
        scores = [x[1] for x in scores_by_day]
        plt.figure(figsize=(10, 5))
        plt.plot(dates, scores, marker='o')
        plt.title(text)
        plt.xticks(rotation=45)
        plt.tight_layout()
        chart_path = f"chart_{user_id}.png"
        plt.savefig(chart_path)
        plt.close()
        await update.message.reply_photo(photo=open(chart_path, "rb"))
        return

    await update.message.reply_text("⏳ لطفاً فقط از گزینه‌های کیبورد استفاده کن یا حالتت رو وارد کن.")

def restart_bot():
    logging.warning("⏱ نیاز به ری‌استارت ربات ولی در محیط محدود هستیم، فقط sleep می‌کنیم.")
    time.sleep(10)

def run_dummy_server():
    import socket
    port = int(os.environ.get("PORT", 10000))  # استفاده از PORT دینامیک مخصوص Render
    class DummyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running.")
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    server.serve_forever()


threading.Thread(target=run_dummy_server).start()

async def main():
    app = ApplicationBuilder().token(TOKEN).read_timeout(10).connect_timeout(10).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("allow", allow))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))

    try:
        await app.run_polling()
    except (TimedOut, NetworkError) as e:
        logging.error(f"❌ خطا در اتصال: {e}")
        restart_bot()
    except Exception as e:
        logging.exception(f"🚨 خطای ناشناخته: {e}")
        time.sleep(5)
        restart_bot()

if __name__ == "__main__":
    import asyncio
    import nest_asyncio
    import threading

    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_dummy_server).start()

    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())


# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     while True:
#         try:
#             app = ApplicationBuilder().token(TOKEN).read_timeout(10).connect_timeout(10).build()
#             app.add_handler(CommandHandler("start", start))
#             app.add_handler(CommandHandler("admin", admin))
#             app.add_handler(CommandHandler("allow", allow))
#             app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all))
#             app.run_polling()
#         except (TimedOut, NetworkError) as e:
#             logging.error(f"❌ خطا در اتصال: {e}")
#             restart_bot()
#         except Exception as e:
#             logging.exception(f"🚨 خطای ناشناخته: {e}")
#             time.sleep(5) 