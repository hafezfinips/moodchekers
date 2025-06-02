import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ContextTypes, filters, CallbackContext)
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os
import asyncio

TOKEN = os.getenv("BOT_TOKEN")  # توکن ربات از متغیر محیطی گرفته می‌شود

TIME_SLOTS = ["صبح", "ظهر", "عصر", "شب", "قبل خواب"]
KEYBOARD = [[slot for slot in TIME_SLOTS], ["وضعیت هفته", "وضعیت ماه"]]
MARKUP = ReplyKeyboardMarkup(KEYBOARD, one_time_keyboard=True, resize_keyboard=True)

NOTIFICATION_TIMES = {
    "صبح": "08:00",
    "ظهر": "12:00",
    "عصر": "17:00",
    "شب": "20:00",
    "قبل خواب": "23:00"
}

DATA_DIR = "userdata"
os.makedirs(DATA_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! حالت چطوره؟ از منوی زیر بازه زمانی رو انتخاب کن و نمره بده 😊", reply_markup=MARKUP)

def get_user_file(user_id):
    return os.path.join(DATA_DIR, f"{user_id}.json")

def load_user_data(user_id):
    path = get_user_file(user_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {"scores": {}, "first_date": datetime.now().strftime("%Y-%m-%d"), "last_slot": None}

def save_user_data(user_id, data):
    with open(get_user_file(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_chart(user_id, period):
    data = load_user_data(user_id)
    scores = data["scores"]
    today = datetime.now()
    if period == "week":
        start_date = today - timedelta(days=6)
    else:
        start_date = today - timedelta(days=29)

    dates = []
    values = []
    for i in range((today - start_date).days + 1):
        date_str = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        daily_scores = scores.get(date_str, {})
        if daily_scores:
            avg = sum(daily_scores.values()) / len(daily_scores)
        else:
            avg = None
        dates.append(date_str)
        values.append(avg)

    if all(v is None for v in values):
        return None

    plt.figure(figsize=(10, 5))
    plt.plot(dates, [v if v is not None else 0 for v in values], marker='o', linestyle='-', color='royalblue')
    plt.fill_between(dates, [v if v is not None else 0 for v in values], color='skyblue', alpha=0.4)
    plt.xticks(rotation=45)
    plt.ylim(0, 10)
    plt.title(f"Mood Trend ({'Week' if period == 'week' else 'Month'})")
    plt.tight_layout()
    filename = f"{DATA_DIR}/chart_{user_id}.png"
    plt.savefig(filename)
    plt.close()
    return filename

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    data = load_user_data(user_id)
    today = datetime.now().strftime("%Y-%m-%d")

    if text in ["وضعیت هفته", "وضعیت ماه"]:
        first_date = datetime.strptime(data["first_date"], "%Y-%m-%d")
        days_passed = (datetime.now() - first_date).days
        required_days = 6 if text == "وضعیت هفته" else 29

        if days_passed < required_days:
            await update.message.reply_text(f"📊 برای گزارش {text} باید حداقل {required_days + 1} روز از شروع ثبت گذشته باشه. هنوز {required_days - days_passed + 1} روز دیگه مونده.")
            return

        period = "week" if text == "وضعیت هفته" else "month"
        path = generate_chart(user_id, period)
        if path:
            await update.message.reply_photo(photo=open(path, "rb"))
        else:
            await update.message.reply_text("داده‌ای برای نمایش وجود نداره.")
        return

    if text in TIME_SLOTS:
        data["last_slot"] = text
        save_user_data(user_id, data)
        await update.message.reply_text(f"الان نمره‌ات برای زمان {text} رو بفرست (بین 1 تا 10)")
        return

    if text.isdigit() and data.get("last_slot"):
        score = int(text)
        if 1 <= score <= 10:
            scores = data.setdefault("scores", {}).setdefault(today, {})
            if data["last_slot"] in scores:
                await update.message.reply_text("برای این بازه قبلاً ثبت کردی.")
                return
            scores[data["last_slot"]] = score
            data["last_slot"] = None
            save_user_data(user_id, data)
            await update.message.reply_text("✅ ثبت شد! ممنون 🌟")
        else:
            await update.message.reply_text("عدد باید بین 1 تا 10 باشه.")
    else:
        await update.message.reply_text("از منوی کیبورد بازه زمانی رو انتخاب کن.")

async def reminder_task(app):
    while True:
        now = datetime.now().strftime("%H:%M")
        for user_file in os.listdir(DATA_DIR):
            if user_file.endswith(".json"):
                user_id = int(user_file.replace(".json", ""))
                data = load_user_data(user_id)
                today = datetime.now().strftime("%Y-%m-%d")
                for slot, slot_time in NOTIFICATION_TIMES.items():
                    if now == slot_time:
                        if today not in data["scores"] or slot not in data["scores"][today]:
                            await app.bot.send_message(chat_id=user_id, text=f"⏰ یادت نره نمره زمان '{slot}' رو ثبت کنی!")
        await asyncio.sleep(60)  # هر 1 دقیقه چک کنه

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_async(reminder_task(app))
    print("ربات اجرا شد...")
    app.run_polling()
