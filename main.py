import threading
import asyncio
import logging
import os
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import BOT_TOKEN, ADMIN_IDS
from db import init_db, add_video, get_video_by_title, get_video_by_id

init_db()

app = Flask(__name__)
@app.route('/')
def home():
    return "麦克视频库运行中！"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= 全新权限校验 =================
async def check_chat_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user_id = update.effective_user.id

    # 1. 私聊：只有开发者（你）能通过
    if chat.type == "private":
        if user_id in ADMIN_IDS:
            return True
        await update.message.reply_text("⚠️ 机器人未开放私聊功能。如需使用，请将机器人拉入你所在的群组。")
        return False

    # 2. 群聊：必须你（7857605443）在这个群是管理员
    is_dev_admin = False
    try:
        for dev_id in ADMIN_IDS:
            member = await context.bot.get_chat_member(chat_id=chat.id, user_id=dev_id)
            if member.status in ['creator', 'administrator']:
                is_dev_admin = True
                break
    except Exception:
        # 如果连你的账号都查不到（说明你被踢了），直接返回无权限
        is_dev_admin = False

    if not is_dev_admin:
        await update.message.reply_text("❌ 该群组无权限。请确保开发者账号在此群组中是管理员。")
        return False

    return True

# ================= 机器人核心功能 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_chat_permission(update, context):
        return

    args = context.args
    if args:
        video_id = args[0]
        file_id = get_video_by_id(video_id)
        if file_id:
            await update.message.reply_text("📹 正在为您发送视频...")
            try:
                # 加入 60 秒超时限制，防止卡半小时
                await asyncio.wait_for(
                    context.bot.send_video(chat_id=update.effective_chat.id, video=file_id),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                await update.message.reply_text("❌ 发送视频超时（网络拥堵），请稍后再次尝试发送电影名。")
            return
    await update.message.reply_text("你好！我是麦克视频库。发送电影名字即可获取视频。")

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_chat_permission(update, context):
        return

    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ 您没有权限上传视频。")
        return

    if not context.args:
        await update.message.reply_text("❌ 格式错误。正确格式：`/upload 电影名字`")
        return

    title = " ".join(context.args)
    context.user_data['pending_upload'] = title
    await update.message.reply_text(f"📤 请发送名为《{title}》的视频文件（请直接发视频）。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_chat_permission(update, context):
        return

    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # 管理员上传/接收视频
    if update.message.video and 'pending_upload' in context.user_data:
        title = context.user_data.pop('pending_upload')
        file_id = update.message.video.file_id
        add_video(title, file_id)
        bot_username = (await context.bot.get_me()).username
        share_link = f"https://t.me/{bot_username}?start={title}"
        await update.message.reply_text(
            f"✅ 视频《{title}》入库成功！\n\n🔗 专属获取链接：\n`{share_link}`\n\n*(用户点击这个链接，或者直接发送电影名都能拿到视频)*",
            parse_mode='Markdown'
        )
        return

    # 普通用户搜索视频（只要你有权限，群里任何人都可以搜）
    file_id = get_video_by_title(text)
    if file_id:
        await update.message.reply_text("📹 正在为您发送视频...")
        try:
            await asyncio.wait_for(
                context.bot.send_video(chat_id=chat_id, video=file_id),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            await update.message.reply_text("❌ 发送视频超时（网络拥堵），请稍后再次尝试发送电影名。")
    else:
        await update.message.reply_text("❌ 没找到这个电影，请检查名字是否正确。")

def start_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("upload", upload_command))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ 麦克机器人已上线！")
    application.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    start_bot()
