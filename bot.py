import os
import sqlite3
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8868824577:AAE-Jyl30HYq8CaVvNgOk2Lm5KQvCJTssZk")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "7582205873"))

CRYPTO_COIN = os.getenv("CRYPTO_COIN", "USDT")
CRYPTO_NETWORK = os.getenv("CRYPTO_NETWORK", "TRON (TRC20)")
CRYPTO_ADDRESS = os.getenv("CRYPTO_ADDRESS", "oxbv")

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

async def start(update, context):
    await update.message.reply_text(
        "🛍️ SOFTWARE STORE\n\nChoose an option:",
        reply_markup=product_keyboard()
    )

async def products_cmd(update, context):
    await update.message.reply_text("🛒 Products:", reply_markup=product_keyboard())

async def myorders_cmd(update, context):
    user_id = update.effective_user.id
    con = db()
    orders = con.execute(
        "SELECT id, product_name, amount_usd, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    recharges = con.execute(
        "SELECT id, bot_username, amount_usd, status, created_at FROM recharge_requests WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)
    ).fetchall()
    con.close()

    lines = ["📦 YOUR ORDERS"]
    if not orders and not recharges:
        lines.append("\nNo orders yet.")
    for o in orders:
        lines.append(f"\n#{o['id']} • {o['product_name']} • {money(o['amount_usd'])}\nStatus: {o['status']}")
    for r in recharges:
        lines.append(f"\n🔄 Recharge #{r['id']} • @{r['bot_username'].lstrip('@')} • $10\nStatus: {r['status']}")
    await update.message.reply_text("\n".join(lines))

async def button(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id

    if q.data == "back":
        await q.edit_message_text("🛒 Products:", reply_markup=product_keyboard())
        return

    if q.data == "my_orders":
        con = db()
        orders = con.execute(
            "SELECT id, product_name, amount_usd, status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (user_id,)
        ).fetchall()
        recharges = con.execute(
            "SELECT id, bot_username, status FROM recharge_requests WHERE user_id=? ORDER BY id DESC LIMIT 20",
            (user_id,)
        ).fetchall()
        con.close()
        lines = ["📦 YOUR ORDERS"]
        if not orders and not recharges:
            lines.append("\nNo orders yet.")
        for o in orders:
            lines.append(f"\n#{o['id']} • {o['product_name']} • {money(o['amount_usd'])}\nStatus: {o['status']}")
        for r in recharges:
            lines.append(f"\n🔄 Recharge #{r['id']} • @{r['bot_username'].lstrip('@')} • $10\nStatus: {r['status']}")
        await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ BACK", callback_data="back")]
        ]))
        return

    if q.data == "notify_manage":
        await q.edit_message_text(
            "🤖 DISCORD NOTIFY BOT\n\n"
            "Manage your subscription here.\n\n"
            "A recharge costs $10.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Recharge Bot — $10", callback_data="recharge")],
                [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                [InlineKeyboardButton("◀️ BACK", callback_data="back")]
            ])
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
        p = PRODUCTS[key]
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
        order_id = int(q.data.split(":")[1])
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
        con.close()

        if not orders and not recharges:
            await q.edit_message_text(
                "🛠 ADMIN PANEL\n\n📭 No pending payment requests.",
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
        buttons += [
            [InlineKeyboardButton("🔄 REFRESH", callback_data="admin_panel")],
            [InlineKeyboardButton("◀️ BACK", callback_data="back")]
        ]

        await q.edit_message_text(
            f"🛠 ADMIN PANEL\n\n"
            f"⏳ Pending orders: {len(orders)}\n"
            f"⏳ Pending recharges: {len(recharges)}\n\n"
            "Select a request below to verify or reject it.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if q.data.startswith("admin_view_order:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        order_id = int(q.data.split(":")[1])
        con = db()
        o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        con.close()
        if not o:
            await q.edit_message_text("Order not found.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
                ]))
            return
        await q.edit_message_text(
            f"🔔 ORDER #{o['id']}\n\n"
            f"Product: {o['product_name']}\n"
            f"Amount: {money(o['amount_usd'])}\n"
            f"Buyer: @{o['username'] or '(none)'}\n"
            f"Telegram ID: {o['user_id']}\n"
            f"TXID: {o['txid']}\n"
            f"Status: {o['status']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY & DELIVER",
                    callback_data=f"admin_verify_order:{order_id}")],
                [InlineKeyboardButton("❌ REJECT",
                    callback_data=f"admin_reject_order:{order_id}")],
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ])
        )
        return

    if q.data.startswith("admin_view_recharge:"):
        if user_id != ADMIN_ID:
            await q.answer("Not authorized.", show_alert=True)
            return
        rid = int(q.data.split(":")[1])
        con = db()
        r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
        con.close()
        if not r:
            await q.edit_message_text("Recharge request not found.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
                ]))
            return
        await q.edit_message_text(
            f"🔄 RECHARGE #{r['id']}\n\n"
            f"Bot username: @{r['bot_username'].lstrip('@')}\n"
            f"Amount: $10\n"
            f"Buyer: @{r['username'] or '(none)'}\n"
            f"Telegram ID: {r['user_id']}\n"
            f"TXID: {r['txid']}\n"
            f"Status: {r['status']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY RECHARGE",
                    callback_data=f"admin_verify_recharge:{rid}")],
                [InlineKeyboardButton("❌ REJECT",
                    callback_data=f"admin_reject_recharge:{rid}")],
                [InlineKeyboardButton("◀️ ADMIN PANEL", callback_data="admin_panel")]
            ])
        )
        return

    if q.data.startswith("admin_verify_order:"):
        if user_id != ADMIN_ID:
            return
        order_id = int(q.data.split(":")[1])
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
            return
        order_id = int(q.data.split(":")[1])
        con = db()
        o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        con.execute("UPDATE orders SET status='payment_rejected' WHERE id=?", (order_id,))
        con.commit()
        con.close()
        await q.edit_message_text(f"❌ Order #{order_id} rejected.")
        if o:
            await context.bot.send_message(o["user_id"], f"❌ Payment for order #{order_id} was not verified. Please contact support.")
        return

    if q.data.startswith("admin_verify_recharge:"):
        if user_id != ADMIN_ID:
            return
        rid = int(q.data.split(":")[1])
        con = db()
        r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
        con.execute("UPDATE recharge_requests SET status='payment_verified' WHERE id=?", (rid,))
        con.commit()
        con.close()
        await q.edit_message_text(f"✅ Recharge #{rid} verified for @{r['bot_username'].lstrip('@')}.")
        if r:
            await context.bot.send_message(
                r["user_id"],
                f"✅ Your $10 recharge for @{r['bot_username'].lstrip('@')} has been verified."
            )
        return

    if q.data.startswith("admin_reject_recharge:"):
        if user_id != ADMIN_ID:
            return
        rid = int(q.data.split(":")[1])
        con = db()
        r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
        con.execute("UPDATE recharge_requests SET status='payment_rejected' WHERE id=?", (rid,))
        con.commit()
        con.close()
        await q.edit_message_text(f"❌ Recharge #{rid} rejected.")
        if r:
            await context.bot.send_message(r["user_id"], f"❌ Recharge #{rid} was not verified.")
        return

async def tx_message(update, context):
    text = (update.message.text or "").strip()
    user_id = update.effective_user.id

    if context.user_data.get("awaiting_bot_username"):
        bot_username = text.lstrip("@").strip()
        if " " in bot_username or len(bot_username) < 3:
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

    kind, ident = target.split(":")
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
            f"📨 TXID received for order #{ident}.\n\n"
            "Status: ⏳ Pending verification\n"
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
            f"📨 TXID received for recharge #{ident}.\n\n"
            "Status: ⏳ Pending verification"
        )
        await notify_admin_recharge(context, ident)

    context.user_data.pop("tx_target", None)

async def notify_admin_order(context, order_id):
    if not ADMIN_ID:
        return
    con = db()
    o = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    con.close()
    if not o:
        return
    await context.bot.send_message(
        ADMIN_ID,
        f"🔔 NEW PAYMENT REQUEST\n\n"
        f"Order #{o['id']}\n"
        f"Product: {o['product_name']}\n"
        f"Amount: {money(o['amount_usd'])}\n"
        f"Buyer: @{o['username'] or '(none)'}\n"
        f"Telegram ID: {o['user_id']}\n"
        f"TXID: {o['txid']}\n"
        f"Status: PENDING VERIFICATION",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ VERIFY & DELIVER", callback_data=f"admin_verify_order:{order_id}")],
            [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_order:{order_id}")]
        ])
    )

async def notify_admin_recharge(context, rid):
    if not ADMIN_ID:
        return
    con = db()
    r = con.execute("SELECT * FROM recharge_requests WHERE id=?", (rid,)).fetchone()
    con.close()
    if not r:
        return
    await context.bot.send_message(
        ADMIN_ID,
        f"🔄 DISCORD NOTIFY BOT RECHARGE\n\n"
        f"Recharge #{r['id']}\n"
        f"Bot username: @{r['bot_username'].lstrip('@')}\n"
        f"Amount: $10\n"
        f"Buyer: @{r['username'] or '(none)'}\n"
        f"Telegram ID: {r['user_id']}\n"
        f"TXID: {r['txid']}\n"
        f"Status: PENDING VERIFICATION",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ VERIFY RECHARGE", callback_data=f"admin_verify_recharge:{rid}")],
            [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_recharge:{rid}")]
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
            f"However, the delivery file `{p['file']}` is not in the products folder yet. "
            "The admin needs to add it.",
            parse_mode="Markdown"
        )
        return

    await context.bot.send_message(o["user_id"], f"✅ Payment verified!\n\nHere is your {p['name']}.")
    with path.open("rb") as f:
        await context.bot.send_document(o["user_id"], document=InputFile(f), caption=f"{p['name']} — Order #{order_id}")

    con = db()
    con.execute("UPDATE orders SET status='delivered' WHERE id=?", (order_id,))
    con.commit()
    con.close()

async def admin_cmd(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ You are not authorized to access the Admin Panel.")
        return
    con = db()
    orders = con.execute(
        "SELECT * FROM orders WHERE status='pending_verification' ORDER BY id DESC"
    ).fetchall()
    recharges = con.execute(
        "SELECT * FROM recharge_requests WHERE status='pending_verification' ORDER BY id DESC"
    ).fetchall()
    con.close()

    if not orders and not recharges:
        await update.message.reply_text("📭 No pending payment requests.")
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
            f"🔄 RECHARGE #{r['id']}\n@{r['bot_username'].lstrip('@')} • $10\n"
            f"Buyer: @{r['username'] or '(none)'}\nTXID: {r['txid']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ VERIFY RECHARGE", callback_data=f"admin_verify_recharge:{r['id']}")],
                [InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_recharge:{r['id']}" )]
            ])
        )

async def admin_products(update, context):
    if update.effective_user.id != ADMIN_ID:
        return
    lines = ["🧰 PRODUCTS CONFIGURED"]
    for key, p in PRODUCTS.items():
        exists = (PRODUCT_DIR / p["file"]).exists()
        lines.append(f"\n{key}\n{p['name']} — {money(p['price_usd'])}\nFile: {p['file']} {'✅' if exists else '❌ MISSING'}")
    lines.append("\nTo add/remove software, edit PRODUCTS in bot.py and put delivery files in the products folder.")
    await update.message.reply_text("\n".join(lines))

async def help_cmd(update, context):
    await update.message.reply_text(
        "/start — store\n/products — products\n/myorders — your orders\n"
        "/admin — admin panel\n/admin_id — check Telegram/admin ID\n"
        "/admin_products — product files\n/help — help"
    )

async def admin_id_cmd(update, context):
    await update.message.reply_text(
        f"Your Telegram ID: {update.effective_user.id}\n"
        f"Configured ADMIN_TELEGRAM_ID: {ADMIN_ID}"
    )

def main():
    if TOKEN == "PASTE_NEW_BOTFATHER_TOKEN_HERE":
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN to your NEW BotFather token.")
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
