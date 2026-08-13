import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, filters, ConversationHandler
)

# =========================================================
# CONFIGURATION
# =========================================================
BOT_TOKEN = "8564093311:AAH55oqI6UmMfXycsEtxtIMjOHNN6atuVoo"
ADMIN_ID = 7813513663
OTP_GROUP_LINK = "https://t.me/X_OTP_service"
SUPPORT_LINK = "https://t.me/Kirito_X69"
DB_FILE = "numbers.db"

# States
CHOOSING_SERVICE, CHOOSING_COUNTRY, WAITING_NUMBERS = range(3)

SERVICES = {
    "telegram": "✈️ TELEGRAM",
    "whatsapp": "🟢 WHATSAPP",
    "facebook": "📘 FACEBOOK",
    "instagram": "📸 INSTAGRAM",
    "tiktok": "🎵 TIKTOK"
}

# =========================================================
# DATABASE SETUP
# =========================================================
db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    service TEXT, 
    country TEXT, 
    number TEXT UNIQUE, 
    used INTEGER DEFAULT 0
)
""")
db.commit()

# =========================================================
# KEYBOARDS (Pure & Clean like your reference)
# =========================================================
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 GET NUMBER", callback_data="get_number"), InlineKeyboardButton("🔍 Search Number", callback_data="search")],
        [InlineKeyboardButton("📊 TRAFFIC", callback_data="traffic"), InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("🆘 SUPPORT", url=SUPPORT_LINK)]
    ])

# =========================================================
# USER /START COMMAND (Clean UI)
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "👑 *NUMBER BOT*\n\n🚀 Welcome to Number & OTP Service\n✅ Choose an option below to continue using the bot."
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_menu(), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=get_main_menu(), parse_mode="Markdown")

# =========================================================
# ADMIN UPLOAD FLOW (/upload command)
# =========================================================
async def admin_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    buttons = [[InlineKeyboardButton(name, callback_data=f"up_serv:{key}")] for key, name in SERVICES.items()]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_upload")])
    await update.message.reply_text("📂 *Admin Panel: Select Service to add stock:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    return CHOOSING_SERVICE

async def admin_service_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['up_service'] = query.data.split(":")[1]
    await query.edit_message_text("✍️ *Now send the Country Name (e.g., Morocco):*", parse_mode="Markdown")
    return CHOOSING_COUNTRY

async def admin_country_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['up_country'] = update.message.text.strip().lower()
    await update.message.reply_text(
        "📥 *Now send numbers directly in chat (one per line) OR upload a `.txt` / `.xlsx` file:*", 
        parse_mode="Markdown"
    )
    return WAITING_NUMBERS

async def process_incoming_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    service = context.user_data.get('up_service')
    country = context.user_data.get('up_country')
    added, duplicate = 0, 0

    lines = []
    # Check if document (file) is sent
    if update.message.document:
        file = await update.message.document.get_file()
        file_path = "temp_stock.txt"
        await file.download_to_drive(file_path)
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                lines = f.readlines()
        except Exception as e:
            await update.message.reply_text(f"❌ File read error: {e}")
            return ConversationHandler.END
    # Check if direct text numbers are sent
    elif update.message.text:
        lines = update.message.text.split("\n")

    for line in lines:
        num = "".join([c for c in line if c.isdigit() or c == '+']).strip()
        if len(num) > 6:
            try:
                db.execute("INSERT INTO numbers (service, country, number, used) VALUES (?, ?, ?, 0)", 
                           (service, country, num))
                added += 1
            except sqlite3.IntegrityError:
                duplicate += 1

    db.commit()
    await update.message.reply_text(
        f"✅ *STOCK UPDATE COMPLETE*\n\n📌 Service: {SERVICES.get(service, service)}\n🌍 Country: {country.upper()}\n➕ Added: {added}\n♻️ Duplicate: {duplicate}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="back_home")]]),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Cancelled")
    await query.edit_message_text("❌ Upload cancelled.", reply_markup=get_main_menu())
    return ConversationHandler.END

# =========================================================
# USER NAVIGATION & GET NUMBER FLOW
# =========================================================
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "back_home":
        text = "👑 *NUMBER BOT*\n\n🚀 Welcome to Number & OTP Service\n✅ Choose an option below to continue using the bot."
        await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode="Markdown")

    elif data == "get_number":
        buttons = [[InlineKeyboardButton(name, callback_data=f"sel_serv:{key}")] for key, name in SERVICES.items()]
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="back_home")])
        await query.edit_message_text("📍 *Select a service:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    
    elif data.startswith("sel_serv:"):
        serv = data.split(":")[1]
        countries = db.execute("SELECT DISTINCT country FROM numbers WHERE service=? AND used=0", (serv,)).fetchall()
        
        if not countries:
            await query.answer("❌ No stock available for this service right now!", show_alert=True)
            return
            
        buttons = [[InlineKeyboardButton(c[0].upper(), callback_data=f"sel_ctry:{serv}:{c[0]}")] for c in countries]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="get_number")])
        await query.edit_message_text(f"📍 *Select a country for {SERVICES.get(serv, serv)}:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data.startswith("sel_ctry:"):
        _, serv, ctry = data.split(":")
        rows = db.execute("SELECT id, number FROM numbers WHERE service=? AND country=? AND used=0 LIMIT 3", (serv, ctry)).fetchall()
        
        if not rows:
            await query.answer("❌ Stock finished for this country!", show_alert=True)
            return

        text = f"📍 {SERVICES.get(serv, serv)} ({ctry.upper()})\n⏳ *Waiting for OTP...*"
        
        buttons = [[InlineKeyboardButton(f"📌 📋 {r[1]}", callback_data=f"copy:{r[1]}")] for r in rows]
        buttons.extend([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"sel_ctry:{serv}:{ctry}"), InlineKeyboardButton("🛡️ OTP Group", url=OTP_GROUP_LINK)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"sel_serv:{serv}")]
        ])
        
        row_ids = [str(r[0]) for r in rows]
        db.execute(f"UPDATE numbers SET used=1 WHERE id IN ({','.join(row_ids)})")
        db.commit()
            
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data == "search":
        await query.answer("🔍 Search feature coming soon!", show_alert=True)
    elif data == "traffic":
        total = db.execute("SELECT COUNT(*) FROM numbers").fetchone()[0]
        used = db.execute("SELECT COUNT(*) FROM numbers WHERE used=1").fetchone()[0]
        await query.answer(f"📊 Total Numbers: {total}\n✅ Used: {used}", show_alert=True)
    elif data == "profile":
        await query.answer(f"👤 Your Telegram ID: {query.from_user.id}", show_alert=True)
    elif data.startswith("copy:"):
        num = data.split(":")[1]
        await query.answer(f"Number: {num}", show_alert=True)

# =========================================================
# RUNNER
# =========================================================
app = Application.builder().token(BOT_TOKEN).build()

upload_conv = ConversationHandler(
    entry_points=[CommandHandler("upload", admin_upload_start)],
    states={
        CHOOSING_SERVICE: [CallbackQueryHandler(admin_service_chosen, pattern="^up_serv:")],
        CHOOSING_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_country_chosen)],
        WAITING_NUMBERS: [
            MessageHandler(filters.Document.ALL | (filters.TEXT & ~filters.COMMAND), process_incoming_numbers)
        ]
    },
    fallbacks=[CallbackQueryHandler(cancel_upload, pattern="^cancel_upload$")]
)

app.add_handler(upload_conv)
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_router))

print("Bot is running perfectly...")
app.run_polling()
