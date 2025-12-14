import json
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import re
from keep_alive import keep_alive
keep_alive()
from telegram import Update, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters
)
ADMIN_IDS = [
    1759155991  # ← ใส่ Telegram User ID ของคุณ
    # ถ้ามีหลายคน เพิ่มได้ เช่น
    # 987654321,
]
COPY_TARGET_USER_ID = 8580689960  # ← Telegram User ID คนที่จะรับเลข

TOKEN = os.getenv("TOKEN")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID"))
DATA_FILE = "balance.json"

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS
# ------------------------------
#  โหลด / บันทึก ยอดคงเหลือ
# ------------------------------
def load_balance():
    if not os.path.exists(DATA_FILE):
        return {"balance": 0, "last_withdraw": 0}

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_balance(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

async def forward_number_with_copy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # จำกัดเฉพาะ ADMIN
    if not is_admin(update):
        return

    # ไม่ทำงานใน TARGET CHAT
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    text = update.message.text.strip()

    # ตรวจสอบเลข 10–12 หลัก
    if not re.fullmatch(r"\d{10,12}", text):
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 คัดลอก", callback_data=f"copy:{text}")]
    ])

    await context.bot.send_message(
        chat_id=COPY_TARGET_USER_ID,
        text=f"{text}",
        reply_markup=keyboard
    )

# ------------------------------
#   คำสั่ง /reset
# ------------------------------
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # ไม่ใช่ admin → เงียบ
    # ❌ ถ้าอยู่ใน TARGET CHAT → ไม่ทำอะไร
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    data = load_balance()
    data["balance"] = 0
    save_balance(data)

    await update.message.reply_text(
        f"ยอดถอน {data['last_withdraw']} บ.\nบช ถอนคงเหลือ 0 บ."
    )


# ------------------------------
#   คำสั่ง /input
# ------------------------------
async def input_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # ไม่ใช่ admin → เงียบ
    # ❌ ไม่ทำงานในกลุ่ม TARGET
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    # ตั้งสถานะว่ากำลังรอจำนวนเงิน
    context.user_data["waiting_input"] = True

    await update.message.reply_text(
        "กรุณาใส่จำนวนเงินที่ต้องการเพิ่ม\n"
        "พิมพ์เป็นตัวเลขอย่างเดียว เช่น\n"
        "10000"
    )


# ------------------------------
#   /cash → ล้างรูปทั้งหมด
# ------------------------------
async def cash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # ไม่ใช่ admin → เงียบ
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    context.user_data["photo_buffer"] = []
    await update.message.reply_text("✔ ล้างรูปทั้งหมดแล้ว")


# ------------------------------
#   /del → ลบรูปล่าสุด 1 รูป
# ------------------------------
async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # ไม่ใช่ admin → เงียบ
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    buffer = context.user_data.get("photo_buffer", [])

    if not buffer:
        await update.message.reply_text("❌ ไม่มีรูปใน buffer")
        return

    buffer.pop()  # ลบรูปล่าสุด
    context.user_data["photo_buffer"] = buffer

    await update.message.reply_text("✔ ลบรูปล่าสุด 1 รูป")


# ------------------------------
#   รับข้อความ → ประมวลผลยอด
# ------------------------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # ไม่ใช่ admin → เงียบ
    # ❌ ถ้าเป็นข้อความในกลุ่ม TARGET CHAT → ไม่ต้องทำอะไรเลย
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    text = update.message.text
    # ✅ กรณีอยู่ในโหมดรอ /input
    if context.user_data.get("waiting_input"):
        if not text.isdigit():
            await update.message.reply_text("❌ กรุณาพิมพ์เป็นตัวเลขเท่านั้น")
            return

        amount = int(text)
        data = load_balance()
        data["balance"] += amount
        save_balance(data)

        # ปิดโหมดรอ
        context.user_data["waiting_input"] = False

        await update.message.reply_text(
            f"✅ เพิ่มยอดสำเร็จ\n"
            f"ยอดถอน {data['last_withdraw']} บ.\n"
            f"บช ถอนคงเหลือ {data['balance']} บ."
        )
        return
    # =========================
    # 2️⃣ เลข 10–12 หลัก → ส่งไปอีกคน + ปุ่ม copy
    # =========================
    if re.fullmatch(r"\d{10,12}", text):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 คัดลอก", callback_data=f"copy:{text}")]
        ])

        await context.bot.send_message(
            chat_id=COPY_TARGET_USER_ID,
            text=f"{text}",
            reply_markup=keyboard
        )
        return
    # =========================
    # 3️⃣ เลขถอนปกติ
    # =========================
    if not text.isdigit():
        return

    amount = int(text)
    data = load_balance()

    data["last_withdraw"] = amount
    data["balance"] -= amount
    if data["balance"] < 0:
        data["balance"] = 0

    save_balance(data)

    reply_msg = (
        f"ยอดถอน {amount} บ.\n"
        f"บช ถอนคงเหลือ {data['balance']} บ."
    )

    context.user_data["last_reply"] = reply_msg

    await update.message.reply_text(reply_msg)


# ------------------------------
#   รับรูป → เก็บ buffer 3 รูป
# ------------------------------
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # ไม่ใช่ admin → เงียบ
    # ❌ ถ้าเป็นรูปในกลุ่ม TARGET CHAT → ไม่ต้องทำอะไร
    if update.effective_chat.id == TARGET_CHAT_ID:
        return

    # สร้าง buffer ถ้ายังไม่มี
    if "photo_buffer" not in context.user_data:
        context.user_data["photo_buffer"] = []

    buffer = context.user_data["photo_buffer"]

    # เก็บ file_id ของรูปใหญ่สุด
    file_id = update.message.photo[-1].file_id
    buffer.append(file_id)

    # ได้ครบ 3 รูปหรือยัง?
    if len(buffer) < 3:
        await update.message.reply_text(f"รูปที่ {len(buffer)}/3")
        return

    # ครบ 3 รูปแล้ว ส่งไปยังกลุ่มเป้าหมาย
    last_reply = context.user_data.get("last_reply", "ไม่มีข้อความล่าสุด")

    media_group = [
        InputMediaPhoto(media=buffer[0]),
        InputMediaPhoto(media=buffer[1]),
        InputMediaPhoto(media=buffer[2])
    ]

    sent_msgs = await context.bot.send_media_group(
        chat_id=TARGET_CHAT_ID,
        media=media_group
    )

    await context.bot.send_message(
        chat_id=TARGET_CHAT_ID,
        text=last_reply,
        reply_to_message_id=sent_msgs[0].message_id
    )

    # ล้าง buffer
    context.user_data["photo_buffer"] = []


# ------------------------------
#   MAIN
# ------------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("input", input_command))
    app.add_handler(CommandHandler("cash", cash_command))
    app.add_handler(CommandHandler("del", del_command))

    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("BOT is running...")
    app.run_polling()


if __name__ == "__main__":

    main()



















