import threading
import asyncio
import logging
import os
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

from config import BOT_TOKEN, ADMIN_IDS
from db import init_db, add_video, get_video_by_title, get_video_by_id, get_all_videos, delete_video_by_id

init_db()

app = Flask(__name__)
@app.route('/')
def home():
    return "麦克视频库运行中！"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ================= 权限校验逻辑 =================
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
    if chat.type == "private":
        return True
    if chat.type in ["group", "supergroup"]:
        if not await is_dev_admin_in_group(context.bot, chat.id):
            await update.message.reply_text("❌ 权限不足：开发者账号在此群组不是管理员，已停止服务。")
            return False
        return True
    return False

# ================= 按钮生成逻辑 =================
def get_main_keyboard():
    keyboard = [[InlineKeyboardButton("📦 查看库中视频", callback_data='list_videos')]]
    return InlineKeyboardMarkup(keyboard)

def get_list_keyboard(videos):
    keyboard = []
    for vid, title in videos:
        keyboard.append([InlineKeyboardButton(title, callback_data=f'detail_{vid}')])
    keyboard.append([InlineKeyboardButton("🔙 返回主菜单", callback_data='back_home')])
    return InlineKeyboardMarkup(keyboard)

def get_detail_keyboard(video_id, is_admin):
    keyboard = [
        [InlineKeyboardButton("▶️ 查看这个视频", callback_data=f'play_{video_id}')]
    ]
    # 只有管理员账号才能看到并点击“删除”按钮
    if is_admin:
        keyboard.append([InlineKeyboardButton("🗑️ 删除这个视频", callback_data=f'delete_{video_id}')])
    keyboard.append([InlineKeyboardButton("🔙 返回列表", callback_data='back_to_list')])
    return InlineKeyboardMarkup(keyboard)

# ================= 机器人核心功能 =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_incoming(update, context):
        return

    args = context.args
    if args:
        video_id = args[0]
        res = get_video_by_id(video_id)
        if res:
            file_id = res[0]
            await update.message.reply_text("📹 正在为您发送视频...")
            try:
                await asyncio.wait_for(
                    context.bot.send_video(chat_id=update.effective_chat.id, video=file_id, supports_streaming=True),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                await update.message.reply_text("❌ 发送视频超时，请稍后重试。")
            return

    # 重置状态
    context.user_data['state'] = 'home'
    await update.message.reply_text(
        "你好！我是麦克视频库。发送电影名字即可获取视频。",
        reply_markup=get_main_keyboard()
    )

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_incoming(update, context):
        return
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ 只有授权管理员拥有上传视频的权限。")
        return
    if not context.args:
        await update.message.reply_text("❌ 格式错误。正确格式：`/upload 电影名字`")
        return
    title = " ".join(context.args)
    context.user_data['pending_upload'] = title
    await update.message.reply_text(f"📤 请发送名为《{title}》的视频文件（请直接发视频）。")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    data = query.data

    if data == 'list_videos':
        videos = get_all_videos()
        if not videos:
            await query.edit_message_text("📭 当前视频库为空，请先使用 `/upload` 上传视频。")
            return
        # 发送新消息，不要编辑原本的主页，否则主页会消失
        await query.message.reply_text("📦 当前视频库：", reply_markup=get_list_keyboard(videos))
        return

    if data == 'back_home':
        await query.message.delete()  # 删掉列表消息
        await start(update, context)
        return

    if data == 'back_to_list':
        videos = get_all_videos()
        await query.edit_message_text("📦 当前视频库：", reply_markup=get_list_keyboard(videos))
        return

    if data.startswith('detail_'):
        video_id = int(data.split('_')[1])
        res = get_video_by_id(video_id)
        if not res:
            await query.edit_message_text("❌ 该视频已从库中删除。")
            return
        title = res[1]
        await query.edit_message_text(
            f"📁 当前选择：{title}",
            reply_markup=get_detail_keyboard(video_id, is_admin)
        )
        return

    if data.startswith('play_'):
        video_id = int(data.split('_')[1])
        res = get_video_by_id(video_id)
        if not res:
            await query.edit_message_text("❌ 视频已被删除。")
            return
        file_id = res[0]
        await query.message.reply_text("📹 正在为您发送视频...")
        try:
            await asyncio.wait_for(
                context.bot.send_video(chat_id=update.effective_chat.id, video=file_id, supports_streaming=True),
                timeout=60.0
            )
        except asyncio.TimeoutError:
            await query.message.reply_text("❌ 发送视频超时，请稍后重试。")
        return

    if data.startswith('delete_'):
        if not is_admin:
            await query.edit_message_text("❌ 你没有删除该视频的权限。")
            return
        video_id = int(data.split('_')[1])
        res = get_video_by_id(video_id)
        if not res:
            await query.edit_message_text("❌ 视频已被删除。")
            return
        title = res[1]
        delete_video_by_id(video_id)
        await query.edit_message_text(f"✅ 视频《{title}》已成功从库中删除。")
        # 自动返回列表
        videos = get_all_videos()
        await query.message.reply_text("📦 当前视频库：", reply_markup=get_list_keyboard(videos))
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_incoming(update, context):
        return

    user_id = update.effective_user.id
    text = update.message.text
    chat_id = update.effective_chat.id

    # 管理员上传视频
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

    # 任何人搜电影
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
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ 麦克视频库已上线！")
    application.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    start_bot()
