from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackContext,
    JobQueue,
)
import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import logging

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7947637241:AAF-zX2Tg97kP26Zr2JP1wgPyGg9sGNJ8-U"  # جایگزین کنید
DB_NAME = "gold_users.db"

# ---- 1. مدیریت دیتابیس ----
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                register_date TEXT
            )
        """)
        conn.commit()
    except Exception as e:
        logger.error(f"خطا در ایجاد دیتابیس: {e}")
    finally:
        conn.close()

# ---- 2. دریافت قیمت از منابع مختلف ----
def fetch_gold_price():
    def get_from_tgju():
        try:
            url = "https://www.tgju.org/profile/geram18"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            gold = soup.find("span", class_="value").get_text(strip=True).replace(",", "")
            gold = int(gold)

            usd_tag = soup.find("a", href="/profile/price_dollar_rl")
            usd_price = usd_tag.find("span", class_="value").get_text(strip=True).replace(",", "")
            usd = int(usd_price)

            ounce_tag = soup.find("a", href="/profile/ons")
            ounce_price = ounce_tag.find("span", class_="value").get_text(strip=True).replace(",", "")
            ounce = float(ounce_price)

            return gold, usd, ounce
        except:
            return None

    def get_from_mesghal():
        try:
            url = "https://www.mesghal.ir/"
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            gold = soup.find("td", text="طلای 18 عیار").find_next_sibling("td").text.strip().replace(",", "")
            gold = int(gold)

            usd = soup.find("td", text="دلار").find_next_sibling("td").text.strip().replace(",", "")
            usd = int(usd)

            ounce = soup.find("td", text="اونس طلا").find_next_sibling("td").text.strip().replace(",", "")
            ounce = float(ounce)

            return gold, usd, ounce
        except:
            return None

    sources = [get_from_tgju, get_from_mesghal]
    for source in sources:
        result = source()
        if result:
            gold, usd, ounce = result
            try:
                calc_gold = int((usd * ounce) / 4.3318)
                now = datetime.datetime.now().strftime("%H:%M")
                return (
                    f"🏅 <b>قیمت لحظه‌ای طلا</b>\n"
                    f"🕒 <b>ساعت:</b> {now}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💰 <b>طلای ۱۸ عیار:</b> {gold:,} تومان\n"
                    f"💵 <b>دلار:</b> {usd:,} تومان\n"
                    f"🌍 <b>اونس جهانی:</b> {ounce:,} دلار\n"
                    f"🧮 <b>قیمت محاسبه‌شده:</b> {calc_gold:,} تومان\n"
                    f"━━━━━━━━━━━━━━"
                )
            except:
                continue

    return "⚠️ خطا در دریافت قیمت از منابع معتبر. لطفاً بعداً تلاش کنید."

# ---- 3. دستورات ربات ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        c.execute(
            "INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
            (user.id, user.username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

        await update.message.reply_text(
            "✅ عضو شدید!\n"
            "قیمت طلا هر ساعت برای شما ارسال می‌شود.\n"
            "برای لغو عضویت /unsubscribe را ارسال کنید."
        )
    except Exception as e:
        logger.error(f"خطا در ثبت کاربر: {e}")
        await update.message.reply_text("⚠️ خطا در ثبت عضویت")
    finally:
        conn.close()

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE chat_id=?", (update.effective_user.id,))
        conn.commit()
        await update.message.reply_text("✅ عضویت شما لغو شد.")
    except Exception as e:
        logger.error(f"خطا در لغو عضویت: {e}")
        await update.message.reply_text("⚠️ خطا در لغو عضویت")
    finally:
        conn.close()

# ---- 4. ارسال خودکار ----
async def send_updates(context: CallbackContext):
    try:
        price = fetch_gold_price()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT chat_id FROM users")

        for (chat_id,) in c.fetchall():
            try:
                await context.bot.send_message(chat_id=chat_id, text=price, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"ارسال به کاربر {chat_id} ناموفق: {e}")
                c.execute("DELETE FROM users WHERE chat_id=?", (chat_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"خطا در ارسال خودکار: {e}")
    finally:
        conn.close()

# ---- 5. راه‌اندازی ----
def main():
    init_db()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))

    job_queue = application.job_queue
    job_queue.run_repeating(
        callback=send_updates,
        interval=3600,  # هر 1 ساعت
        first=10
    )

    logger.info("ربات قیمت طلا فعال شد")
    application.run_polling()

if __name__ == "__main__":
    main()

