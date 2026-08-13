import sqlite3
import openpyxl
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
SERVICE, COUNTRY, UPLOAD = range(3)

# Services & Mapping
SERVICES = {
    "telegram": "✈️ TELEGRAM",
    "whatsapp": "🟢 WHATSAPP",
    "facebook": "📘 FACEBOOK",
    "tiktok": "🎵 TIKTOK"
}

# =========================================================
# DATABASE SETUP
# =========================================================
db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS numbers (id INTEGER PRIMARY KEY AUTOINCREMENT, service TEXT, country TEXT, number TEXT UNIQUE, used INTEGER DEFAULT 0)")
db.commit()

# =========================================================
# KEYBOARD LAYOUTS (HUbUHU MATCHING YOUR REFERENCE)
# =========================================================
def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 GET NUMBER", callback_data="get_number"), InlineKeyboardButton("🔍 Search Number", callback_data="search")],
        [InlineKeyboardButton("📊 TRAFFIC", callback_data="traffic"), InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("🆘 SUPPORT", url=SUPPORT_LINK)]
    ])

# =========================================================
# ADMIN UPLOAD HANDLERS
# =========================================================
async def start_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    buttons = [[InlineKeyboardButton(name, callback_data=f"up_serv:{key}")] for key, name in SERVICES.items()]
    await update.message.reply_text("📂 *Select Service to add stock:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    return SERVICE

async def admin_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data['s'] = query.data.split(":")[1]
    await query.edit_message_text("✍️ *Enter Country Name (e.g., Morocco):*", parse_mode="Markdown")
    return COUNTRY

async def admin_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['c'] = update.message.text.strip().lower()
    await update.message.reply_text("📤 *Now upload the .txt or .xlsx file:*", parse_mode="Markdown")
    return UPLOAD

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    await file.download_to_drive("temp.txt")
    
    service, country = context.user_data['s'], context.user_data['c']
    count = 0
    with open("temp.txt", "r", encoding="latin-1") as f:
        for line in f:
            num = "".join(filter(str.isdigit, line))
            if len(num) > 6:
                try:
                    db.execute("INSERT INTO numbers (service, country, number) VALUES (?, ?, ?)", (service, country, num))
                    count += 1
                except: continue
    db.commit()
    await update.message.reply_text(f"✅ *Added {count} numbers to {service.upper()} ({country.upper()})!*", parse_mode="Markdown")
    return ConversationHandler.END

# =========================================================
# USER HANDLERS
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👑 *NUMBER BOT*\n\n🚀 Welcome to Number & OTP Service\n✅ Choose an option below:", 
                                    reply_markup=get_main_menu(), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "get_number":
        buttons = [[InlineKeyboardButton(name, callback_data=f"sel_serv:{key}")] for key, name in SERVICES.items()]
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="start")])
        await query.edit_message_text("📍 *Select a service:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    
    elif data.startswith("sel_serv:"):
        serv = data.split(":")[1]
        countries = db.execute("SELECT DISTINCT country FROM numbers WHERE service=? AND used=0", (serv,)).fetchall()
        buttons = [[InlineKeyboardButton(c[0].upper(), callback_data=f"sel_ctry:{serv}:{c[0]}")] for c in countries]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="get_number")])
        await query.edit_message_text(f"📍 *Select country for {serv.upper()}:*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data.startswith("sel_ctry:"):
        _, serv, ctry = data.split(":")
        rows = db.execute("SELECT id, number FROM numbers WHERE service=? AND country=? AND used=0 LIMIT 3", (serv, ctry)).fetchall()
        
        text = f"🇷🇪 {serv.upper()} ({ctry.upper()})\n⏳ *Waiting for OTP...*"
        buttons = [[InlineKeyboardButton(f"📋 {r[1]}", callback_data="noop")] for r in rows]
        buttons.extend([
            [InlineKeyboardButton("🔄 Change Number", callback_data=f"sel_ctry:{serv}:{ctry}"), InlineKeyboardButton("🛡️ OTP Group", url=OTP_GROUP_LINK)],
            [InlineKeyboardButton("🔙 Back", callback_data="get_number")]
        ])
        
        # নাম্বারগুলো মার্ক করা
        if rows:
            db.execute(f"UPDATE numbers SET used=1 WHERE id IN ({','.join([str(r[0]) for r in rows])})")
            db.commit()
            
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")

    elif data == "start":
        await query.edit_message_text("👑 *NUMBER BOT*\n\n🚀 Welcome to Number & OTP Service\n✅ Choose an option below:", 
                                    reply_markup=get_main_menu(), parse_mode="Markdown")

# =========================================================
# RUNNER
# =========================================================
app = Application.builder().token(BOT_TOKEN).build()
conv = ConversationHandler(entry_points=[CommandHandler("upload", start_upload)], 
                           states={SERVICE: [CallbackQueryHandler(admin_service)], COUNTRY: [MessageHandler(filters.TEXT, admin_country)], UPLOAD: [MessageHandler(filters.Document.ALL, handle_file)]},
                           fallbacks=[])
app.add_handler(conv)
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
print("Bot started...")
app.run_polling()
