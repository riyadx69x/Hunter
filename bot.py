import os
import re
import csv
import sqlite3
from io import BytesIO

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CopyTextButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = "8564093311:AAH55oqI6UmMfXycsEtxtIMjOHNN6atuVoo"
ADMIN_ID = 7813513663

DB_FILE = "numbers.db"

SERVICES = {
    "telegram": "✈️ Telegram",
    "whatsapp": "🟢 WhatsApp",
    "tiktok": "🎵 TikTok",
}

# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS numbers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    country TEXT NOT NULL,
    number TEXT NOT NULL UNIQUE,
    used INTEGER DEFAULT 0,
    added_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    claimed INTEGER DEFAULT 0
)
""")

db.commit()


def db_execute(query, params=(), fetch=False):
    cur = db.cursor()
    cur.execute(query, params)
    db.commit()

    if fetch:
        return cur.fetchall()

    return None


# =========================================================
# KEYBOARDS
# =========================================================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📞 GET NUMBER",
                callback_data="get_number"
            ),
            InlineKeyboardButton(
                "🔎 SEARCH NUMBER",
                callback_data="search"
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 TRAFFIC",
                callback_data="traffic"
            ),
            InlineKeyboardButton(
                "👤 MY PROFILE",
                callback_data="profile"
            ),
        ],
        [
            InlineKeyboardButton(
                "🆘 SUPPORT",
                callback_data="support"
            )
        ]
    ])


def service_menu():
    buttons = []

    for key, name in SERVICES.items():
        buttons.append([
            InlineKeyboardButton(
                name,
                callback_data=f"service:{key}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("❌ Close", callback_data="close")
    ])

    return InlineKeyboardMarkup(buttons)


def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="main")]
    ])


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    db_execute("""
        INSERT OR IGNORE INTO users(user_id, claimed)
        VALUES (?, 0)
    """, (user.id,))

    text = (
        "🤖 *NUMBER STOCK BOT*\n\n"
        "Welcome! Select an option below:"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


# =========================================================
# CALLBACKS
# =========================================================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    # MAIN
    if data == "main":
        await query.edit_message_text(
            "🤖 *NUMBER STOCK BOT*\n\nSelect an option:",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return

    # CLOSE
    if data == "close":
        await query.edit_message_text(
            "❌ Menu closed.\n\nUse /start to open again."
        )
        return

    # GET NUMBER
    if data == "get_number":
        await query.edit_message_text(
            "📍 *Select a service:*",
            parse_mode="Markdown",
            reply_markup=service_menu()
        )
        return

    # SERVICE
    if data.startswith("service:"):
        service = data.split(":", 1)[1]

        rows = db_execute("""
            SELECT DISTINCT country
            FROM numbers
            WHERE service = ? AND used = 0
            ORDER BY country
        """, (service,), fetch=True)

        if not rows:
            await query.edit_message_text(
                "❌ No numbers available for this service.",
                reply_markup=back_button()
            )
            return

        buttons = []

        for (country,) in rows:
            buttons.append([
                InlineKeyboardButton(
                    f"🌍 {country}",
                    callback_data=f"country:{service}:{country}"
                )
            ])

        buttons.append([
            InlineKeyboardButton("⬅️ Back", callback_data="get_number")
        ])

        await query.edit_message_text(
            f"📍 *Select a country for {SERVICES.get(service, service)}:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # COUNTRY
    if data.startswith("country:"):
        parts = data.split(":", 2)

        if len(parts) != 3:
            return

        service = parts[1]
        country = parts[2]

        rows = db_execute("""
            SELECT id, number
            FROM numbers
            WHERE service = ?
              AND country = ?
              AND used = 0
            ORDER BY id
            LIMIT 3
        """, (service, country), fetch=True)

        if not rows:
            await query.edit_message_text(
                "❌ No numbers available.",
                reply_markup=back_button()
            )
            return

        # Reserve these numbers
        ids = [row[0] for row in rows]

        placeholders = ",".join(["?"] * len(ids))

        db_execute(
            f"""
            UPDATE numbers
            SET used = 1
            WHERE id IN ({placeholders})
            """,
            ids
        )

        # User statistics
        db_execute("""
            INSERT OR IGNORE INTO users(user_id, claimed)
            VALUES (?, 0)
        """, (query.from_user.id,))

        db_execute("""
            UPDATE users
            SET claimed = claimed + ?
            WHERE user_id = ?
        """, (len(rows), query.from_user.id))

        text = (
            f"{SERVICES.get(service, service)} *({country})*\n"
            f"📦 Numbers available: {len(rows)}\n\n"
            "Tap a number to copy it:"
        )

        buttons = []

        for _, number in rows:
            buttons.append([
                InlineKeyboardButton(
                    f"📋 {number}",
                    copy_text=CopyTextButton(text=number)
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔄 Change Number",
                callback_data=f"country:{service}:{country}"
            ),
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data=f"service:{service}"
            )
        ])

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # SEARCH
    if data == "search":
        context.user_data["search_mode"] = True

        await query.edit_message_text(
            "🔎 *Search Number*\n\n"
            "Send the starting digits/prefix.\n\n"
            "Example:\n"
            "`880178`",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        return

    # PROFILE
    if data == "profile":
        user_id = query.from_user.id

        claimed_row = db_execute("""
            SELECT claimed
            FROM users
            WHERE user_id = ?
        """, (user_id,), fetch=True)

        claimed = claimed_row[0][0] if claimed_row else 0

        total = db_execute("""
            SELECT COUNT(*)
            FROM numbers
            WHERE used = 0
        """, fetch=True)[0][0]

        await query.edit_message_text(
            "👤 *MY PROFILE*\n\n"
            f"🆔 User ID: `{user_id}`\n"
            f"📦 Numbers claimed: *{claimed}*\n"
            f"📊 Current stock: *{total}*",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        return

    # TRAFFIC
    if data == "traffic":
        rows = db_execute("""
            SELECT service,
                   COUNT(*) AS total,
                   SUM(CASE WHEN used=1 THEN 1 ELSE 0 END) AS used
            FROM numbers
            GROUP BY service
        """, fetch=True)

        text = "📊 *TRAFFIC / STOCK*\n\n"

        for service, total, used in rows:
            available = total - (used or 0)

            text += (
                f"{SERVICES.get(service, service)}\n"
                f"• Total: {total}\n"
                f"• Used: {used or 0}\n"
                f"• Available: {available}\n\n"
            )

        if not rows:
            text += "No stock yet."

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        return

    # SUPPORT
    if data == "support":
        await query.edit_message_text(
            "🆘 *SUPPORT*\n\n"
            "For support, contact the administrator.",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        return


# =========================================================
# SEARCH HANDLER
# =========================================================

async def search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("search_mode"):
        return

    prefix = update.message.text.strip()

    if not re.fullmatch(r"\+?\d{3,15}", prefix):
        await update.message.reply_text(
            "❌ Invalid prefix.\nSend digits only, for example:\n`880178`",
            parse_mode="Markdown"
        )
        return

    context.user_data["search_mode"] = False

    rows = db_execute("""
        SELECT service, country, number
        FROM numbers
        WHERE used = 0
          AND number LIKE ?
        ORDER BY id
        LIMIT 20
    """, (prefix + "%",), fetch=True)

    if not rows:
        await update.message.reply_text(
            "❌ No available number found.",
            reply_markup=main_menu()
        )
        return

    text = f"🔎 *Search results for:* `{prefix}`\n\n"

    buttons = []

    for service, country, number in rows:
        text += (
            f"{SERVICES.get(service, service)} — "
            f"{country} — `{number}`\n"
        )

        buttons.append([
            InlineKeyboardButton(
                f"📋 {number}",
                copy_text=CopyTextButton(text=number)
            )
        ])

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data="main")
    ])

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========================================================
# ADMIN
# =========================================================

def is_admin(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Your Telegram ID:\n`{update.effective_user.id}`",
        parse_mode="Markdown"
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    text = (
        "👑 *ADMIN PANEL*\n\n"
        "Send a `.txt` or `.csv` file containing numbers.\n\n"
        "Format:\n"
        "`service|country|number`\n\n"
        "Example:\n"
        "`telegram|Malaysia|+60123456789`\n"
        "`whatsapp|Bangladesh|+8801XXXXXXXXX`\n"
        "`tiktok|France|+33XXXXXXXXX`"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================================================
# FILE UPLOAD
# =========================================================

async def file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    document = update.message.document

    if not document:
        return

    filename = document.file_name or ""

    if not filename.lower().endswith((".txt", ".csv")):
        await update.message.reply_text(
            "❌ Only .txt or .csv files are supported."
        )
        return

    tg_file = await document.get_file()
    data = await tg_file.download_as_bytearray()

    added = 0
    duplicate = 0
    invalid = 0

    try:
        content = bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError:
        content = bytes(data).decode("latin-1")

    lines = content.splitlines()

    for line in lines:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "|" in line:
            parts = [x.strip() for x in line.split("|")]
        else:
            try:
                parts = next(csv.reader([line]))
                parts = [x.strip() for x in parts]
            except Exception:
                invalid += 1
                continue

        if len(parts) < 3:
            invalid += 1
            continue

        service = parts[0].lower()
        country = parts[1]
        number = parts[2].strip()

        if service not in SERVICES:
            invalid += 1
            continue

        if not re.fullmatch(r"\+?\d{6,20}", number):
            invalid += 1
            continue

        try:
            db_execute("""
                INSERT INTO numbers(
                    service,
                    country,
                    number,
                    used,
                    added_by
                )
                VALUES (?, ?, ?, 0, ?)
            """, (
                service,
                country,
                number,
                update.effective_user.id
            ))

            added += 1

        except sqlite3.IntegrityError:
            duplicate += 1

    await update.message.reply_text(
        "✅ *STOCK UPDATE COMPLETE*\n\n"
        f"➕ Added: {added}\n"
        f"♻️ Duplicate: {duplicate}\n"
        f"❌ Invalid: {invalid}",
        parse_mode="Markdown"
    )


# =========================================================
# ADMIN RESET USED STOCK
# =========================================================

async def reset_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return

    db_execute("""
        UPDATE numbers
        SET used = 0
    """)

    await update.message.reply_text(
        "✅ All numbers have been marked available again."
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(update, context):
    print("ERROR:", context.error)


# =========================================================
# MAIN
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Set it as an environment variable."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("resetstock", reset_stock))

    app.add_handler(
        CallbackQueryHandler(callbacks)
    )

    app.add_handler(
        MessageHandler(
            filters.Document.ALL,
            file_upload
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            search_message
        )
    )

    app.add_error_handler(error_handler)

    print("Bot is running...")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
