import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import json
from datetime import datetime
import matplotlib.pyplot as plt

# 🔐 توکن ربات (فقط برای تست پروژه فعلی، در پروژه‌های عمومی هرگز توکن رو داخل کد نذار)
TOKEN = "6733614053:AAEtTx1WWbEXZSmqcb1M--_W2tdjcC2fsYc"

# کیبورد سفارشی
reply_keyboard = [["صبح", "ظهر", "عصر", "شب", "قبل خواب"], ["وضعیت هفته", "وضعیت ماه"]]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)

# ثبت نمره توسط کاربر
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! امروز حالت چطوره؟ یک عدد بین 1 تا 10 بفرست 😊", reply_markup=markup
    )

# ذخیره نمره
def save_score(user_id, score):
    today = datetime.now().strftime("%Y-%m-%d")
    data = {}
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        pass

    if str(user_id) not in data:
        data[str(user_id)] = {}

    data[str(user_id)][today] = score

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# رسم نمودار
def generate_chart(user_id):
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    user_data = data.get(str(user_id), {})
    items = sorted(user_data.items())
    dates = [item[0] for item in items][-14:]
    scores = [int(item[1]) for item in items][-14:]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, scores, marker='o', linestyle='-', color='#4CAF50', linewidth=2)
    plt.fill_between(dates, scores, color='#E8F5E9', alpha=0.5)
    plt.title("🔷 روند نمره‌های ۱۴ روز اخیر", fontsize=14, fontweight='bold')
    plt.xlabel("تاریخ", fontsize=12)
    plt.ylabel("نمره از ۱۰", fontsize=12)
    plt.ylim(0, 10)
    plt.xticks(rotation=45)
    plt.grid(visible=True, which='both', axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()
    filename = f"stats_{user_id}.png"
    plt.savefig(filename)
    plt.close()
    return filename

# هندل پیام‌ها
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text in ["وضعیت هفته", "وضعیت ماه"]:
        chart_path = generate_chart(user_id)
        await update.message.reply_photo(photo=open(chart_path, "rb"))
    elif text.isdigit():
        score = int(text)
        if 1 <= score <= 10:
            save_score(user_id, score)
            await update.message.reply_text("✅ ثبت شد! ممنون 🌟")
        else:
            await update.message.reply_text("عدد باید بین 1 تا 10 باشه.")
    else:
        await update.message.reply_text("لطفاً یک عدد بین 1 تا 10 وارد کن.")

# اجرای بات
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("ربات در حال اجراست...")
    app.run_polling()
