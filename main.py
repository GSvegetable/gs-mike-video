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

# ================= 权限校验逻辑（群聊与私聊分离） =================

# 群聊必须检测“你(7857605443)”是否在群内且为管理员
async def is_dev_admin_in_group(bot, chat_id):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=7857605443)
        if member.status in ['creator', 'administrator']:
            return True
    except Exception:
        pass
    return False

async def handle_incoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user_id = update.effective_user.id
    
    # 情况A：如果是私聊
    if chat.type == "private":
        return True # 私聊任何人都不拦截，能不能上传看后面的逻辑
        
    # 情况B：如果是群聊
    if chat.type in ["group", "supergroup"]:
        # 必须确保 7857605443 是管理员
        if not await is_dev_admin_in_group(context.bot, chat.id):
            # 给你发个提示，通知群里人你不在群里当管理员了
            await update.message.reply_text("❌ 权限不足：开发者账号在此群组不是管理员，已停止服务。")
            return False
        # 只有你的号在群里是管理员，群员才能使用搜索功能
        return True
        
    return False

# ================= 机器人核心功能 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 进入前先过权限门
    if not await handle_incoming(update, context):
        return

    args = context.args
    if args:
        video_id = args[0]
        file_id = get_video_by_id(video_id)
        if file_id:
            await update.message.reply_text("📹 正在为您发送视频...")
            try:
                await asyncio.wait_for(
                    context.bot.send_video(chat_id=update.effective_chat.id, video=file_id, supports_streaming=True),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                await update.message.reply_text("❌ 发送视频超时（网络拥堵），请稍后再次尝试发送电影名。")
            return
    await update.message.reply_text("你好！我是麦克视频库。发送电影名字即可获取视频。")

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 进入前先过权限门
    if not await handle_incoming(update, context):
        return

    user_id = update.effective_user.id
    # 只有你或朋友（ADMIN_IDS）才有上传资格
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ 只有授权管理员拥有上传视频的权限。")
        return

    if not context.args:
        await update.message.reply_text("❌ 格式错误。正确格式：`/upload 电影名字`")
        return

    title = " ".join(context.args)
    context.user_data['pending_upload'] = title
    await update.message.reply_text(f"📤 请发送名为《{title}》的视频文件（请直接发视频）。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 进入前先过权限门
    if not await handle_incoming(update, context):
        return

    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # 1. 上传逻辑（仅在是 ADMIN_IDS 发起，且带有上传状态时触发）
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

    # 2. 搜视频逻辑（无论是群里的群员，还是私聊的陌生人，只要过了权限门都能搜）
    file_id = get_video_by_title(text)
    if file_id:
        await update.message.reply_text("📹 正在为您发送视频...")
        try:
            await asyncio.wait_for(
                context.bot.send_video(chat_id=chat_id, video=file_id, supports_streaming=True),
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
