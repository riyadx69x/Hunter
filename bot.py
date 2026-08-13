import sqlite3
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, filters, ConversationHandler
)

# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = "8564093311:AAH55oqI6UmMfXycsEtxtIMjOHNN6atuVoo"
ADMIN_ID = 7813513663  # তোমার টেলিগ্রাম আইডি
OTP_GROUP_LINK = "https://t.me/X_OTP_service"
SUPPORT_LINK = "https://t.me/Kirito_X69"
DB_FILE = "numbers.db"

# কনভার্সেশন স্টেট (অ্যাডমিন আপলোডের জন্য)
SERVICE, COUNTRY, UPLOAD = range(3)

# কান্ট্রি ফ্ল্যাগ ডিকশনারি
COUNTRY_FLAGS = {
    "morocco": "🇲🇦",
    "ukraine": "🇺🇦",
    "iraq": "🇮🇶",
    "sudan": "🇸🇩",
    "afghanistan": "🇦🇫",
    "bangladesh": "🇧🇩",
    "india": "🇮🇳",
    "france": "🇫🇷",
    "malaysia": "🇲🇾",
    "whatsapp": "🟢",
    "telegram": "✈️"
}

SERVICES = {
    "whatsapp": "🟢 WHATSAPP",
    "telegram": "✈️ TELEGRAM",
    "facebook": "📘 FACEBOOK",
    "tiktok": "🎵 TIKTOK",
}

# =========================================================
# DATABASE SETUP
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    country TEXT NOT NULL,
    number TEXT NOT NULL UNIQUE,
    used INTEGER DEFAULT 0
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    claimed INTEGER DEFAULT 0
)
""")
db.commit()

def is_admin(user_id):
    return user_id == ADMIN_ID

# =========================================================
# ADMIN UPLOAD CONVERSATION HANDLERS
# =========================================================

async def start_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ You are not authorized!")
        return ConversationHandler.END
    
    buttons = []
    for key, name in SERVICES.items():
        buttons.append([InlineKeyboardButton(name, callback_data=f"up_serv:{key}")])
    
    await update.message.reply_text(
        "📂 *Select Service for Upload:*", 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return SERVICE

async def admin_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    service_key = query.data.split(":")[1]
    context.user_data['upload_service'] = service_key
    
    await query.edit_message_text(
        f"✅ Selected Service: *{SERVICES.get(service_key, service_key)}*\n\n"
        "✍️ *Now send the Country Name (e.g., Morocco):*", 
        parse_mode="Markdown"
    )
    return COUNTRY

async def admin_select_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    country_name = update.message.text.strip().lower()
    context.user_data['upload_country'] = country_name
    
    await update.message.reply_text(
        f"✅ Country: *{country_name.upper()}*\n\n"
        "📤 *Now send/upload your `.txt` or `.xlsx` file containing the numbers:*", 
        parse_mode="Markdown"
    )
    return UPLOAD

async def admin_handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return ConversationHandler.END

    document = update.message.document
    if not document:
        await update.message.reply_text("❌ Please upload a valid file!")
        return UPLOAD

    tg_file = await document.get_file()
    file_path = "temp_upload_file"
    await tg_file.download_to_drive(file_path)

    service = context.user_data.get('upload_service')
    country = context.user_data.get('upload_country')

    added = 0
    duplicate = 0
    invalid = 0

    try:
        # ফাইলটি .xlsx হলে Pandas দিয়ে পড়বো, অন্যথায় টেক্সট ফাইল হিসেবে পড়বো
        if document.file_name.endswith('.xlsx'):
            df = pd.read_excel(file_path)
            numbers = df.iloc[:, 0].astype(str).tolist()
        else:
            with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                numbers = [line.strip() for line in f if line.strip()]

        for number in numbers:
            number = number.strip()
            if not number or number.startswith("#"):
                continue
            try:
                db.execute("INSERT INTO numbers (service, country, number, used) VALUES (?, ?, ?, 0)", (service, country, number))
                added += 1
            except sqlite3.IntegrityError:
                duplicate += 1
            except Exception:
                invalid += 1

        db.commit()
    except Exception as e:
        await update.message.reply_text(f"❌ Error reading file: {e}")
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ *STOCK UPDATE COMPLETE*\n\n"
        f"📌 Service: *{SERVICES.get(service, service)}*\n"
        f"🌍 Country: *{country.upper()}*\n"
        f"➕ Added: {added}\n"
        f"♻️ Duplicate: {duplicate}\n"
        f"❌ Invalid: {invalid}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Upload cancelled.")
    return ConversationHandler.END

# =========================================================
# USER / GENERAL HANDLERS
# =========================================================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📞 GET NUMBER", callback_data="get_number"),
            InlineKeyboardButton("🔎 Search Number", callback_data="search")
        ],
        [
            InlineKeyboardButton("📊 TRAFFIC", callback_data="traffic"),
            InlineKeyboardButton("🟢 My Profile", callback_data="profile")
        ],
        [
            InlineKeyboardButton("🆘 SUPPORT", url=SUPPORT_LINK)
        ]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.execute("INSERT OR IGNORE INTO users(user_id, claimed) VALUES (?, 0)", (user.id,))
    db.commit()
    
    text = (
        "👑 *NUMBER BOT*\n\n"
        "🌐 *Welcome to Number & OTP Service*\n\n"
        "✅ *Choose an option below to continue using the bot.*\n\n"
        "💎 *Premium OTP Service*"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "main":
        await query.edit_message_text(
            "👑 *NUMBER BOT*\n\n"
            "🌐 *Welcome to Number & OTP Service*\n\n"
            "✅ *Choose an option below to continue using the bot.*\n\n"
            "💎 *Premium OTP Service*",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return

    if data == "get_number":
        buttons = []
        for key, name in SERVICES.items():
            buttons.append([InlineKeyboardButton(name, callback_data=f"user_serv:{key}")])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="main")])
        
        await query.edit_message_text(
            "📍 *Select a service:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("user_serv:"):
        service = data.split(":")[1]
        rows = db.execute("SELECT DISTINCT country FROM numbers WHERE service = ? AND used = 0 ORDER BY country", (service,)).fetchall()
        
        if not rows:
            await query.edit_message_text(
                "❌ No numbers available for this service right now.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="get_number")]])
            )
            return

        buttons = []
        for (country,) in rows:
            flag = COUNTRY_FLAGS.get(country.lower(), "🌍")
            buttons.append([InlineKeyboardButton(f"{flag} {country.upper()}", callback_data=f"user_country:{service}:{country}")])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="get_number")])

        await query.edit_message_text(
            f"📍 *Select a country for {SERVICES.get(service, service)}:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data.startswith("user_country:"):
        parts = data.split(":")
        if len(parts) != 3:
            return
        
        service = parts[1]
        country = parts[2]

        rows = db.execute("SELECT id, number FROM numbers WHERE service = ? AND country = ? AND used = 0 ORDER BY id LIMIT 3", (service, country)).fetchall()
        
        if not rows:
            await query.edit_message_text(
                "❌ No numbers available for this country.", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f"user_serv:{service}")]])
            )
            return

        ids = [row[0] for row in rows]
        placeholders = ",".join(["?"] * len(ids))
        db.execute(f"UPDATE numbers SET used = 1 WHERE id IN ({placeholders})", ids)
        db.commit()

        user_id = query.from_user.id
        db.execute("INSERT OR IGNORE INTO users(user_id, claimed) VALUES (?, 0)", (user_id,))
        db.execute("UPDATE users SET claimed = claimed + ? WHERE user_id = ?", (len(rows), user_id))
        db.commit()

        flag = COUNTRY_FLAGS.get(country.lower(), "🌍")
        service_name = SERVICES.get(service, service).split()[-1]
        
        text = (
            f"⏳ *Waiting for OTP...*\n\n"
            f"📱 *{service_name} ({country.capitalize()})*"
        )

        buttons = []
        for _, number in rows:
            buttons.append([InlineKeyboardButton(f"{flag} {number}", copy_text=CopyTextButton(text=number))])

        # বাটনগুলো ঠিক স্ক্রিনশটের স্টাইলে নিচে সেট করা হলো
        buttons.append([
            InlineKeyboardButton("🔄 Change Number", callback_data=f"user_country:{service}:{country}"),
            InlineKeyboardButton("🌐 OTP Group", url=OTP_GROUP_LINK)
        ])
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"user_serv:{service}")])

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data == "profile":
        user_id = query.from_user.id
        claimed_row = db.execute("SELECT claimed FROM users WHERE user_id = ?", (user_id,)).fetchone()
        claimed = claimed_row[0] if claimed_row else 0
        total = db.execute("SELECT COUNT(*) FROM numbers WHERE used = 0").fetchone()[0]

        await query.edit_message_text(
            "👤 *MY PROFILE*\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📦 Numbers claimed: *{claimed}*\n"
            f"📊 Current stock: *{total}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main")]])
        )
        return

    if data == "traffic":
        rows = db.execute("SELECT service, COUNT(*), SUM(CASE WHEN used=1 THEN 1 ELSE 0 END) FROM numbers GROUP BY service").fetchall()
        text = "📊 *TRAFFIC / STOCK*\n\n"
        for service, total, used in rows:
            available = total - (used or 0)
            text += f"{SERVICES.get(service, service)}\n• Total: {total}\n• Available: {available}\n\n"
        if not rows:
            text += "No stock available yet."
        
        await query.edit_message_text(
            text, 
            parse_mode="Markdown", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main")]])
        )
        return

    if data == "search":
        await query.edit_message_text(
            "🔎 *Search Number*\n\nFeature coming soon or use GET NUMBER.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="main")]])
        )
        return

# =========================================================
# MAIN APP RUNNER
# =========================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    upload_conv = ConversationHandler(
        entry_points=[CommandHandler("upload", start_upload)],
        states={
            SERVICE: [CallbackQueryHandler(admin_select_service, pattern="^up_serv:")],
            COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_select_country)],
            UPLOAD: [MessageHandler(filters.Document.ALL, admin_handle_file)]
        },
        fallbacks=[CommandHandler("cancel", cancel_upload)]
    )

    app.add_handler(upload_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))

    print("Bot is running successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
