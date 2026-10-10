import os
import sqlite3
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger(__name__)

# Set TELEGRAM_BOT_TOKEN in your environment. Do not hardcode your bot token.
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "7582205873"))

CRYPTO_COIN = os.getenv("CRYPTO_COIN", "USDT")
CRYPTO_NETWORK = os.getenv("CRYPTO_NETWORK", "TRON (TRC20)")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS", "TQKr4erMHBrf3FETzFPnAtPkvMKvLQDnXR")

DB = Path("store.db")
PRODUCT_DIR = Path("products")
PRODUCT_DIR.mkdir(exist_ok=True)

PRODUCTS = {
    "screenconnect": {
        "name": "ScreenConnect", "price_usd": 1500,
        "description": "Remote screensharing software",
        "file": "ScreenConnect.exe",
    },
    "Stock Broker": {
        "name": "Stock Broker", "price_usd": 800,
        "description": "copytraders,wallet connect,live trading",
        "file": "Stock.exe",
    },
    "crypto Broker": {
        "name": "crypto Broker", "price_usd": 300,
        "description": "wallet connect,live trading",
        "file": "crypto.exe",
    },
    "Online Banking": {
        "name": "Online Banking ", "price_usd": 500,
        "description": "transfer,account statement,loan",
        "file": "bank.exe",
    },
    "Consignment": {
        "name": "Consignment", "price_usd": 200,
        "description": "shipping id,tracking",
        "file": "shipping.exe",
    },
    "Real Estate": {
        "name": "Real Estate", "price_usd": 600,
        "description": " ",
        "file": "shipping.exe",
    },
    "NFT": {
        "name": "NFT", "price_usd": 700,
        "description": " ",
        "file": "shipping.exe",
    },
    "discord_notify": {
        "name": "Discord Notify Bot", "price_usd": 150,
        "description": "Instant notification",
        "file": "DiscordNotifyBot.zip",
    },
    "twitterbot": {
        "name": "TwitterBot", "price_usd": 150,
        "description": "Auto follow and auto messaging",
        "file": "TwitterBot.zip",
    },
    "server_hunter": {
        "name": "Discord Server Hunter", "price_usd": 100,
        "description": "Discord server hunter",
        "file": "DiscordServerHunter.zip",
    },
    "wallet_swap": {
        "name": "Wallet Swap", "price_usd": 1500,
        "description": "DM",
        "file": "WalletSwap.zip",
    },
}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        product_key TEXT NOT NULL,
        product_name TEXT NOT NULL,
        amount_usd REAL NOT NULL,
        txid TEXT,
        status TEXT NOT NULL DEFAULT 'awaiting_payment',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS recharge_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        bot_username TEXT NOT NULL,
        amount_usd REAL NOT NULL DEFAULT 10,
        txid TEXT,
        status TEXT NOT NULL DEFAULT 'awaiting_payment',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS fix_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        bot_username TEXT NOT NULL,
        complaint TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        fixed_at DATETIME
    );
    """)
    con.commit()
    con.close()


def money(x):
    return f"${x:,.0f}"


def product_keyboard():
    rows = []
    for key, p in PRODUCTS.items():
        rows.append([InlineKeyboardButton(
            f"{p['name']} — {money(p['price_usd'])}",
            callback_data=f"product:{key}"
        )])
    rows.append([InlineKeyboardButton("🤖 Manage Discord Notify Bot", callback_data="notify_manage")])
    rows.append([InlineKeyboardButton("📦 My Orders", callback_data="my_orders")])
    rows.append([InlineKeyboardButton("🛠 ADMIN PANEL", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)


def payment_text(title, amount, extra=""):
    address = CRYPTO_ADDRESS
    return (
        f"💳 PAYMENT FOR {title}\n\n"
        f"Amount: {money(amount)}\n"
        f"Coin: {CRYPTO_COIN}\n"
        f"Network: {CRYPTO_NETWORK}\n\n"
        f"Wallet address:\n`{address}`\n\n"
        "⚠️ Send only the specified coin on the specified network.\n"
        "After sending, press PAYMENT SENT and submit your TXID.\n"
        "The order remains pending until the admin verifies the blockchain transaction."
        + extra
    )


def my_orders_text(user_id):
    con = db()
    orders = con.execute(
        "SELECT id, product_name, amount_usd, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    recharges = con.execute(
        "SELECT id, bot_username, amount_usd, status, created_at FROM recharge_requests WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    fixes = con.execute(
        "SELECT id, bot_username, status, created_at FROM fix_requests WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    con.close()

    lines = ["📦 YOUR ORDERS"]
    if not orders and not recharges and not fixes:
        lines.append("\nNo orders or support requests yet.")
    for o in orders:
        lines.append(f"\n#{o['id']} • {o['product_name']} • {money(o['amount_usd'])}\nStatus: {o['status']}")
    for r in recharges:
        lines.append(f"\n🔄 Recharge #{r['id']} • @{r['bot_username'].lstrip('@')} • {money(r['amount_usd'])}\nStatus: {r['status']}")
    for f in fixes:
        lines.append(
            f"\n🔧 Fix Request #{f['id']} • @{f['bot_username'].lstrip('@')}"
            f"\nStatus: {f['status'].upper()}"
        )
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛍️ SOFTWARE STORE\n\nChoose an option:",
        reply_markup=product_keyboard()
    )


async def products_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 Products:", reply_markup=product_keyboard())


async def myorders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(my_orders_text(update.effective_user.id))


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    if q.data == "back":
        await q.edit_message_text("🛒 Products:", reply_markup=product_keyboard())
        return

    if q.data == "my_orders":
        await q.edit_message_text(
            my_orders_text(user_id),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ BACK", callback_data="back")]
            ])
        )
        return

    if q.data == "notify_manage":
        await q.edit_message_text(
            "🤖 DISCORD NOTIFY BOT\n\n"
            "Manage your subscription or report a problem here.\n\n"
            "A recharge costs $10.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Recharge Bot — $10", callback_data="recharge")],
                [InlineKeyboardButton("🔧 Fix It", callback_data="fix_it")],
                [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                [InlineKeyboardButton("◀️ BACK", callback_data="back")]
            ])
        )
        return

    if q.data == "fix_it":
        context.user_data["fix_step"] = "bot_username"
        context.user_data.pop("fix_bot_username", None)
        await q.edit_message_text(
            "🔧 FIX DISCORD NOTIFY BOT\n\n"
            "Step 1 of 2\n"
            "Enter your Discord Notify Bot username."
        )
        return

    if q.data.startswith("product:"):
        key = q.data.split(":", 1)[1]
        p = PRODUCTS.get(key)
        if not p:
            await q.edit_message_text("Product unavailable.")
            return
        await q.edit_message_text(
            f"🛍️ {p['name']}\n\n"
            f"💰 Price: {money(p['price_usd'])}\n\n"
            f"📄 {p['description']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🪙 BUY WITH CRYPTO", callback_data=f"buy:{key}")],
                [InlineKeyboardButton("◀️ BACK", callback_data="back")]
            ])
        )
        return

    if q.data.startswith("buy:"):
        key = q.data.split(":", 1)[1]
        p = PRODUCTS.get(key)
        if not p:
            await q.edit_message_text("Product unavailable.")
            return
        con = db()
        cur = con.execute(
            "INSERT INTO orders (user_id, username, product_key, product_name, amount_usd) VALUES (?, ?, ?, ?, ?)",
            (user_id, q.from_user.username or "", key, p["name"], p["price_usd"])
        )
        order_id = cur.lastrowid
        con.commit()
        con.close()
        context.user_data["active_order"] = order_id
        await q.edit_message_text(
            f"🧾 ORDER #{order_id}\n\n" + payment_text(p["name"], p["price_usd"]),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ PAYMENT SENT", callback_data=f"payment_sent:{order_id}")],
                [InlineKeyboardButton("◀️ BACK", callback_data="back")]
            ])
        )
        return

    if q.data.startswith("payment_sent:"):
        order_id = int(q.data.split(":", 1)[1])
        context.user_data["tx_target"] = f"order:{order_id}"
        await q.edit_message_text(
            f"✍️ Order #{order_id}\n\nSend the transaction ID (TXID) as your next message.\n\n"
            "Never send your seed phrase or private key."
        )
        return

    if q.data == "recharge":
        context.user_data["awaiting_bot_username"] = True
        await q.edit_message_text(
            "🤖 RECHARGE DISCORD NOTIFY BOT\n\n"
            "Send the Discord bot username you want to recharge (for example: @MyNotifyBot)."
        )
        return

    if q.data == "admin_panel":
        if user_id != ADMIN_ID:
            await q.edit_message_text(
                "⛔ You are not authorized to access the Admin Panel.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ BACK", callback_data="back")]
                ])
            )
            return

        con = db()
        orders = con.execute(
            "SELECT * FROM orders WHERE status='pending_verification' ORDER BY id DESC"
        ).fetchall()
        recharges = con.execute(
            "SELECT * FROM recharge_requests WHERE status='pending_verification' ORDER BY id DESC"
        ).fetchall()
        fixes = con.execute(
            "SELECT * FROM fix_requests WHERE status='open' ORDER BY id DESC"
        ).fetchall()
        con.close()

        if not orders and not recharges and not fixes:
            await q.edit_message_text(
                "🛠 ADMIN PANEL\n\n📭 No pending orders, recharges, or fix requests.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="admin_panel")],
                    [InlineKeyboardButton("◀️ BACK", callback_data="back")]
                ])
            )
            return

        buttons = []
        for o in orders:
            buttons.append([InlineKeyboardButton(
                f"🛒 Order #{o['id']} — {o['product_name']}",
                callback_data=f"admin_view_order:{o['id']}"
            )])
        for r in recharges:
            buttons.append([InlineKeyboardButton(
                f"🔄 Recharge #{r['id']} — @{r['bot_username'].lstrip('@')}",
                callback_data=f"admin_view_recharge:{r['id']}"
            )])
        for f in fixes:
            buttons.append([InlineKeyboardButton(
                f"🔧 Fix #{f['id']} — @{f['bot_username'].lstrip('@')}",
                callback_data=f"admin_view_fix:{f['id']}"
            )])
        buttons += [
            [InlineKeyboardButton("🔄 REFRESH", callback_data="admin_panel")],
            [InlineKeyboardButton("◀️ BACK", callback_data="back")]
        ]

        await q.edit_message_text(
            "🛠 ADMIN PANEL\n\n"
            f"⏳ Pending orders: {len(orders)}\n"
            f"⏳ Pending recharges: {len(recharges)}\n"
            f"🔧 Open fix requests: {len(fixes)}\n\n"
            "Select a request to review.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if q.data.startswith("admin_view_order:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        order_id = int(q.data.split(":", 1)[1])
        con = db()
        o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        con.close()
        if not o:
            await q.edit_message_text("Order not found.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ]))
            return
        await q.edit_message_text(
            f"🔔 ORDER #{o['id']}\n\n"
            f"Product: {o['product_name']}\n"
            f"Amount: {money(o['amount_usd'])}\n"
            f"Buyer: @{o['username'] or '(none)'}\n"
            f"Telegram ID: {o['user_id']}\n"
            f"TXID: {o['txid'] or '(not submitted)'}\n"
            f"Status: {o['status']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY & DELIVER", callback_data=f"admin_verify_order:{order_id}")],
                [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_order:{order_id}")],
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ])
        )
        return

    if q.data.startswith("admin_view_recharge:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        rid = int(q.data.split(":", 1)[1])
        con = db()
        r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
        con.close()
        if not r:
            await q.edit_message_text("Recharge request not found.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ]))
            return
        await q.edit_message_text(
            f"🔄 RECHARGE #{r['id']}\n\n"
            f"Bot username: @{r['bot_username'].lstrip('@')}\n"
            f"Amount: {money(r['amount_usd'])}\n"
            f"Buyer: @{r['username'] or '(none)'}\n"
            f"Telegram ID: {r['user_id']}\n"
            f"TXID: {r['txid'] or '(not submitted)'}\n"
            f"Status: {r['status']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY RECHARGE", callback_data=f"admin_verify_recharge:{rid}")],
                [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_recharge:{rid}")],
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ])
        )
        return

    if q.data.startswith("admin_view_fix:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        fix_id = int(q.data.split(":", 1)[1])
        con = db()
        f = con.execute("SELECT * FROM fix_requests WHERE id=?", (fix_id,)).fetchone()
        con.close()
        if not f:
            await q.edit_message_text("Fix request not found.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ]))
            return
        buttons = []
        if f["status"] != "fixed":
            buttons.append([InlineKeyboardButton(
                "✅ VERIFY FIX COMPLETED", callback_data=f"admin_verify_fix:{fix_id}"
            )])
        buttons.append([InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")])
        await q.edit_message_text(
            f"🔧 FIX REQUEST #{f['id']}\n\n"
            f"Bot username: @{f['bot_username'].lstrip('@')}\n"
            f"Complaint:\n{f['complaint']}\n\n"
            f"User: @{f['username'] or '(no Telegram username)'}\n"
            f"Telegram ID: {f['user_id']}\n"
            f"Submitted: {f['created_at']}\n"
            f"Status: {f['status'].upper()}"
            + (f"\nFixed at: {f['fixed_at']}" if f["fixed_at"] else ""),
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if q.data.startswith("admin_verify_order:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        order_id = int(q.data.split(":", 1)[1])
        con = db()
        o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not o:
            con.close()
            await q.edit_message_text("Order not found.")
            return
        con.execute("UPDATE orders SET status='payment_verified' WHERE id=?", (order_id,))
        con.commit()
        con.close()
        await q.edit_message_text(f"✅ Order #{order_id} verified.")
        await deliver_product(context, order_id)
        return

    if q.data.startswith("admin_reject_order:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        order_id = int(q.data.split(":", 1)[1])
        con = db()
        o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if o:
            con.execute("UPDATE orders SET status='payment_rejected' WHERE id=?", (order_id,))
            con.commit()
        con.close()
        await q.edit_message_text(f"❌ Order #{order_id} rejected.")
        if o:
            await context.bot.send_message(o["user_id"], f"❌ Payment for order #{order_id} was not verified. Please contact support.")
        return

    if q.data.startswith("admin_verify_recharge:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        rid = int(q.data.split(":", 1)[1])
        con = db()
        r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
        if not r:
            con.close()
            await q.edit_message_text("Recharge request not found.")
            return
        con.execute("UPDATE recharge_requests SET status='payment_verified' WHERE id=?", (rid,))
        con.commit()
        con.close()
        await q.edit_message_text(f"✅ Recharge #{rid} verified for @{r['bot_username'].lstrip('@')}.")
        await context.bot.send_message(
            r["user_id"],
            f"✅ Your {money(r['amount_usd'])} recharge for @{r['bot_username'].lstrip('@')} has been verified."
        )
        return

    if q.data.startswith("admin_reject_recharge:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        rid = int(q.data.split(":", 1)[1])
        con = db()
        r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
        if r:
            con.execute("UPDATE recharge_requests SET status='payment_rejected' WHERE id=?", (rid,))
            con.commit()
        con.close()
        await q.edit_message_text(f"❌ Recharge #{rid} rejected.")
        if r:
            await context.bot.send_message(r["user_id"], f"❌ Recharge #{rid} was not verified.")
        return

    if q.data.startswith("admin_verify_fix:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        fix_id = int(q.data.split(":", 1)[1])
        con = db()
        f = con.execute("SELECT * FROM fix_requests WHERE id=?", (fix_id,)).fetchone()
        if not f:
            con.close()
            await q.edit_message_text("Fix request not found.")
            return
        if f["status"] == "fixed":
            con.close()
            await q.answer("This fix request has already been verified.", show_alert=True)
            return
        con.execute(
            "UPDATE fix_requests SET status='fixed', fixed_at=CURRENT_TIMESTAMP WHERE id=?",
            (fix_id,)
        )
        con.commit()
        con.close()
        await q.edit_message_text(
            f"✅ FIX REQUEST #{fix_id} VERIFIED\n\n"
            f"Bot: @{f['bot_username'].lstrip('@')}\nStatus: FIXED"
        )
        try:
            await context.bot.send_message(
                chat_id=f["user_id"],
                text=(
                    f"✅ YOUR FIX HAS BEEN VERIFIED\n\n"
                    f"Request: #{fix_id}\n"
                    f"Bot: @{f['bot_username'].lstrip('@')}\n\n"
                    "The admin has marked your support request as fixed."
                )
            )
        except Exception:
            log.exception("Could not notify user about fix request %s", fix_id)
        return


async def tx_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    # Fix It support flow is handled before transaction IDs and recharge usernames.
    fix_step = context.user_data.get("fix_step")
    if fix_step == "bot_username":
        bot_username = text.lstrip("@").strip()
        if not bot_username or len(bot_username) > 100 or any(ch.isspace() for ch in bot_username):
            await update.message.reply_text(
                "Please enter a valid bot username without spaces, for example @MyNotifyBot."
            )
            return
        context.user_data["fix_bot_username"] = bot_username
        context.user_data["fix_step"] = "complaint"
        await update.message.reply_text(
            "📝 Step 2 of 2\n\n"
            "Describe the problem with your bot. Include what is happening and what you expected to happen."
        )
        return

    if fix_step == "complaint":
        complaint = text
        if len(complaint) < 5:
            await update.message.reply_text("Please describe the problem in at least 5 characters.")
            return
        if len(complaint) > 3000:
            await update.message.reply_text("Please keep your complaint under 3,000 characters.")
            return
        bot_username = context.user_data.get("fix_bot_username")
        if not bot_username:
            context.user_data.pop("fix_step", None)
            await update.message.reply_text("Your support session expired. Please select Fix It again.")
            return

        con = db()
        cur = con.execute(
            "INSERT INTO fix_requests (user_id, username, bot_username, complaint) VALUES (?, ?, ?, ?)",
            (user_id, update.effective_user.username or "", bot_username, complaint)
        )
        fix_id = cur.lastrowid
        con.commit()
        con.close()
        context.user_data.pop("fix_step", None)
        context.user_data.pop("fix_bot_username", None)

        await update.message.reply_text(
            f"✅ FIX REQUEST #{fix_id} SUBMITTED\n\n"
            f"Bot: @{bot_username}\n"
            "Status: OPEN\n\n"
            "Your complaint has been forwarded to the admin. You will receive a notification when the fix is verified."
        )
        try:
            await notify_admin_fix(context, fix_id)
        except Exception:
            log.exception("Failed to notify admin about fix request %s", fix_id)
            await update.message.reply_text(
                "Your request was saved, but the admin notification could not be delivered. Please contact support."
            )
        return

    if context.user_data.get("awaiting_bot_username"):
        bot_username = text.lstrip("@").strip()
        if " " in bot_username or len(bot_username) < 3 or len(bot_username) > 100:
            await update.message.reply_text("Please send a valid Discord bot username, e.g. @MyNotifyBot.")
            return
        con = db()
        cur = con.execute(
            "INSERT INTO recharge_requests (user_id, username, bot_username) VALUES (?, ?, ?)",
            (user_id, update.effective_user.username or "", bot_username)
        )
        rid = cur.lastrowid
        con.commit()
        con.close()
        context.user_data.pop("awaiting_bot_username", None)
        context.user_data["tx_target"] = f"recharge:{rid}"
        await update.message.reply_text(
            f"🔄 RECHARGE #{rid}\n\n"
            + payment_text(f"Discord Notify Bot recharge for @{bot_username}", 10)
            + "\n\nAfter paying, send the TXID here.",
            parse_mode="Markdown"
        )
        return

    target = context.user_data.get("tx_target")
    if not target:
        return

    if len(text) < 8 or len(text) > 200 or any(ch.isspace() for ch in text):
        await update.message.reply_text("Please send the transaction ID as one continuous string.")
        return

    kind, ident = target.split(":", 1)
    ident = int(ident)
    con = db()

    if kind == "order":
        o = con.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (ident, user_id)).fetchone()
        if not o:
            con.close()
            await update.message.reply_text("Order not found.")
            return
        con.execute("UPDATE orders SET txid=?, status='pending_verification' WHERE id=?", (text, ident))
        con.commit()
        con.close()
        await update.message.reply_text(
            f"📨 TXID received for order #{ident}.\n\nStatus: ⏳ Pending verification\n"
            "An admin will verify the transaction before delivery."
        )
        await notify_admin_order(context, ident)

    elif kind == "recharge":
        r = con.execute("SELECT * FROM recharge_requests WHERE id=? AND user_id=?", (ident, user_id)).fetchone()
        if not r:
            con.close()
            await update.message.reply_text("Recharge request not found.")
            return
        con.execute("UPDATE recharge_requests SET txid=?, status='pending_verification' WHERE id=?", (text, ident))
        con.commit()
        con.close()
        await update.message.reply_text(
            f"📨 TXID received for recharge #{ident}.\n\nStatus: ⏳ Pending verification"
        )
        await notify_admin_recharge(context, ident)
    else:
        con.close()
        await update.message.reply_text("Unknown request type. Please start again from the menu.")
        context.user_data.pop("tx_target", None)
        return

    context.user_data.pop("tx_target", None)


async def notify_admin_order(context, order_id):
    con = db()
    o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    con.close()
    if not o:
        return
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 NEW PAYMENT REQUEST\n\n"
        f"Order #{o['id']}\nProduct: {o['product_name']}\nAmount: {money(o['amount_usd'])}\n"
        f"Buyer: @{o['username'] or '(none)'}\nTelegram ID: {o['user_id']}\nTXID: {o['txid']}\n"
        "Status: PENDING VERIFICATION",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ VERIFY & DELIVER", callback_data=f"admin_verify_order:{order_id}")],
            [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_order:{order_id}")]
        ])
    )


async def notify_admin_recharge(context, rid):
    con = db()
    r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
    con.close()
    if not r:
        return
    await context.bot.send_message(
        ADMIN_ID,
        f"🔄 DISCORD NOTIFY BOT RECHARGE\n\n"
        f"Recharge #{r['id']}\nBot username: @{r['bot_username'].lstrip('@')}\n"
        f"Amount: {money(r['amount_usd'])}\nBuyer: @{r['username'] or '(none)'}\n"
        f"Telegram ID: {r['user_id']}\nTXID: {r['txid']}\nStatus: PENDING VERIFICATION",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ VERIFY RECHARGE", callback_data=f"admin_verify_recharge:{rid}")],
            [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_recharge:{rid}")]
        ])
    )


async def notify_admin_fix(context, fix_id):
    con = db()
    f = con.execute("SELECT * FROM fix_requests WHERE id=?", (fix_id,)).fetchone()
    con.close()
    if not f:
        return
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🔧 NEW BOT FIX REQUEST #{f['id']}\n\n"
            f"Bot username: @{f['bot_username'].lstrip('@')}\n"
            f"Complaint:\n{f['complaint']}\n\n"
            f"User: @{f['username'] or '(no Telegram username)'}\n"
            f"Telegram ID: {f['user_id']}\n"
            f"Submitted: {f['created_at']}\nStatus: {f['status'].upper()}"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ VERIFY FIX COMPLETED", callback_data=f"admin_verify_fix:{fix_id}")],
            [InlineKeyboardButton("📋 View Request", callback_data=f"admin_view_fix:{fix_id}")]
        ])
    )


async def deliver_product(context, order_id):
    con = db()
    o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    con.close()
    if not o:
        return
    p = PRODUCTS.get(o["product_key"])
    if not p:
        await context.bot.send_message(o["user_id"], "Payment verified, but the product is no longer configured. Contact support.")
        return

    path = PRODUCT_DIR / p["file"]
    if not path.exists():
        await context.bot.send_message(
            o["user_id"],
            f"✅ Payment verified for order #{order_id}.\n\n"
            f"However, the delivery file `{p['file']}` is not in the products folder yet. The admin needs to add it.",
            parse_mode="Markdown"
        )
        return

    await context.bot.send_message(o["user_id"], f"✅ Payment verified!\n\nHere is your {p['name']}.")
    with path.open("rb") as f:
        await context.bot.send_document(
            o["user_id"], document=InputFile(f), caption=f"{p['name']} — Order #{order_id}"
        )

    con = db()
    con.execute("UPDATE orders SET status='delivered' WHERE id=?", (order_id,))
    con.commit()
    con.close()


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ You are not authorized to access the Admin Panel.")
        return

    con = db()
    orders = con.execute("SELECT * FROM orders WHERE status='pending_verification' ORDER BY id DESC").fetchall()
    recharges = con.execute("SELECT * FROM recharge_requests WHERE status='pending_verification' ORDER BY id DESC").fetchall()
    fixes = con.execute("SELECT * FROM fix_requests WHERE status='open' ORDER BY id DESC").fetchall()
    con.close()

    if not orders and not recharges and not fixes:
        await update.message.reply_text("📭 No pending orders, recharges, or fix requests.")
        return

    for o in orders:
        await update.message.reply_text(
            f"🔔 ORDER #{o['id']}\n{o['product_name']} • {money(o['amount_usd'])}\n"
            f"Buyer: @{o['username'] or '(none)'}\nTXID: {o['txid']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY & DELIVER", callback_data=f"admin_verify_order:{o['id']}")],
                [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_order:{o['id']}")]
            ])
        )

    for r in recharges:
        await update.message.reply_text(
            f"🔄 RECHARGE #{r['id']}\n@{r['bot_username'].lstrip('@')} • {money(r['amount_usd'])}\n"
            f"Buyer: @{r['username'] or '(none)'}\nTXID: {r['txid']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY RECHARGE", callback_data=f"admin_verify_recharge:{r['id']}")],
                [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_recharge:{r['id']}")]
            ])
        )

    for f in fixes:
        await update.message.reply_text(
            f"🔧 FIX REQUEST #{f['id']}\nBot: @{f['bot_username'].lstrip('@')}\n\n"
            f"Complaint:\n{f['complaint']}\n\n"
            f"User: @{f['username'] or '(no Telegram username)'}\nTelegram ID: {f['user_id']}\n"
            f"Status: {f['status'].upper()}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY FIX COMPLETED", callback_data=f"admin_verify_fix:{f['id']}")],
                [InlineKeyboardButton("📋 VIEW REQUEST", callback_data=f"admin_view_fix:{f['id']}")]
            ])
        )


async def admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ You are not authorized.")
        return
    lines = ["🧰 PRODUCTS CONFIGURED"]
    for key, p in PRODUCTS.items():
        exists = (PRODUCT_DIR / p["file"]).exists()
        lines.append(f"\n{key}\n{p['name']} — {money(p['price_usd'])}\nFile: {p['file']} {'✅' if exists else '❌ MISSING'}")
    lines.append("\nTo add/remove software, edit PRODUCTS in bot.py and put delivery files in the products folder.")
    await update.message.reply_text("\n".join(lines))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — store\n/products — products\n/myorders — your orders and fix requests\n"
        "/admin — admin panel\n/admin_id — check Telegram/admin ID\n"
        "/admin_products — product files\n/help — help"
    )


async def admin_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Your Telegram ID: {update.effective_user.id}\n"
        f"Configured ADMIN_TELEGRAM_ID: {ADMIN_ID}"
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "Set TELEGRAM_BOT_TOKEN in your environment before starting the bot. "
            "Do not hardcode the token in bot.py."
        )
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products_cmd))
    app.add_handler(CommandHandler("myorders", myorders_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("admin_id", admin_id_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("admin_products", admin_products))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tx_message))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
