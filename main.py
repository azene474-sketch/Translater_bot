import os
import json
import asyncio
import shutil
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from deep_translator import GoogleTranslator

# ===== التوكن والبوت =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_YOUR_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "PUT_YOUR_ADMIN_ID"))

DB_FILE = "data.json"
BACKUP_DIR = "backups"

# ===== إعداد ملف البيانات والنسخ الاحتياطية =====
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"users": [], "channels": []}, f, ensure_ascii=False, indent=4)

def load_data():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    # إنشاء نسخة احتياطية قبل الحفظ
    create_backup()
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def create_backup():
    """إنشاء نسخة احتياطية من ملف البيانات"""
    if os.path.exists(DB_FILE):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"data_backup_{timestamp}.json")
        shutil.copy2(DB_FILE, backup_file)
        # الاحتفاظ بآخر 10 نسخ احتياطية فقط
        cleanup_old_backups()

def cleanup_old_backups():
    """حذف النسخ الاحتياطية القديمة والاحتفاظ بآخر 10 نسخ"""
    try:
        backup_files = []
        for file in os.listdir(BACKUP_DIR):
            if (file.startswith("data_backup_") or file.startswith("manual_backup_")) and file.endswith(".json"):
                backup_files.append(os.path.join(BACKUP_DIR, file))
        
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # حذف النسخ الزائدة عن 10
        for backup_file in backup_files[10:]:
            os.remove(backup_file)
    except:
        pass

def get_backup_files():
    """الحصول على قائمة بملفات النسخ الاحتياطية"""
    try:
        backup_files = []
        for file in os.listdir(BACKUP_DIR):
            if (file.startswith("data_backup_") or file.startswith("manual_backup_")) and file.endswith(".json"):
                backup_files.append(file)
        backup_files.sort(reverse=True)
        return backup_files[:5]  # إرجاع آخر 5 نسخ
    except:
        return []

def restore_backup(backup_filename):
    """استعادة نسخة احتياطية"""
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, DB_FILE)
            return True
    except:
        pass
    return False

def manual_backup():
    """إنشاء نسخة احتياطية يدوية"""
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"manual_backup_{timestamp}.json")
        shutil.copy2(DB_FILE, backup_file)
        # تنظيف النسخ القديمة للحفاظ على المساحة
        cleanup_old_backups()
        return backup_file
    except:
        return None

def add_user(user_id):
    data = load_data()
    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

def get_all_users():
    return load_data()["users"]

def add_channel(channel_username):
    data = load_data()
    if channel_username not in data["channels"]:
        data["channels"].append(channel_username)
        save_data(data)

def remove_channel(channel_username):
    data = load_data()
    if channel_username in data["channels"]:
        data["channels"].remove(channel_username)
        save_data(data)

def get_all_channels():
    return load_data()["channels"]

# ===== تحديد لغة الترجمة =====
def choose_target_lang(detected_lang: str) -> str:
    return "en" if detected_lang.startswith("ar") else "ar"

# ===== التحقق من الاشتراك بالقنوات =====
async def get_unsubscribed_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channels = get_all_channels()
    unsubscribed = []
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed.append(channel)
        except:
            unsubscribed.append(channel)
    return unsubscribed

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    unsubscribed = await get_unsubscribed_channels(update, context)
    if unsubscribed:
        channels_text = "\n".join(unsubscribed)
        await update.message.reply_text(
            f"⚠️ يجب الاشتراك في جميع القنوات التالية للحصول على الخدمة:\n{channels_text}"
        )
        return False
    return True

# ===== لوحة التحكم للمستخدم =====
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 ترجمة نص", callback_data="translate_text")],
        [InlineKeyboardButton("ℹ️ معلومات عن البوت", callback_data="about")],
    ]
    if update.effective_user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🛠 لوحة تحكم الأدمِن", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("مرحباً! اختر خياراً:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("مرحباً! اختر خياراً:", reply_markup=reply_markup)

# ===== /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if not await check_subscription(update, context):
            return
        add_user(user_id)
    await show_menu(update, context)

# ===== التعامل مع الأزرار =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # التحقق من الاشتراك للمستخدم العادي
    if user_id != ADMIN_ID:
        unsubscribed = await get_unsubscribed_channels(update, context)
        if unsubscribed:
            channels_text = "\n".join(unsubscribed)
            await query.edit_message_text(
                f"⚠️ يجب الاشتراك في جميع القنوات التالية للحصول على الخدمة:\n{channels_text}"
            )
            return

    if data == "translate_text":
        await query.edit_message_text("✏️ أرسل لي النص الذي تريد ترجمته:")
        context.user_data["mode"] = "translate"
    elif data == "about":
        await query.edit_message_text("🤖 هذا بوت لترجمة النصوص بين العربية والإنجليزية.")
    elif data == "admin_panel" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 عدد المشتركين", callback_data="admin_count")],
            [InlineKeyboardButton("📣 إرسال رسالة جماعية", callback_data="admin_broadcast")],
            [InlineKeyboardButton("➕ إضافة قناة اشتراك", callback_data="admin_add_channel")],
            [InlineKeyboardButton("➖ إزالة قناة اشتراك", callback_data="admin_remove_channel")],
            [InlineKeyboardButton("📌 عرض قنوات الاشتراك", callback_data="admin_show_channels")],
            [InlineKeyboardButton("💾 إنشاء نسخة احتياطية", callback_data="admin_create_backup")],
            [InlineKeyboardButton("📂 استعادة نسخة احتياطية", callback_data="admin_restore_backup")],
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🛠 لوحة تحكم الأدمِن:", reply_markup=reply_markup)
    elif data == "admin_count" and user_id == ADMIN_ID:
        users = get_all_users()
        await query.edit_message_text(f"📊 عدد المشتركين في البوت: {len(users)}")
    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        await query.edit_message_text("✏️ أرسل لي الرسالة التي تريد إرسالها لجميع المشتركين:")
        context.user_data["mode"] = "broadcast"
    elif data == "admin_add_channel" and user_id == ADMIN_ID:
        await query.edit_message_text("✏️ أرسل @اسم_القناة لإضافتها كشرط اشتراك:")
        context.user_data["mode"] = "add_channel"
    elif data == "admin_remove_channel" and user_id == ADMIN_ID:
        channels = get_all_channels()
        if not channels:
            await query.edit_message_text("⚠️ لا توجد قنوات لتتم إزالتها.")
            return
        keyboard = [[InlineKeyboardButton(ch, callback_data=f"remove_{ch}")] for ch in channels]
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("اختر القناة التي تريد إزالتها:", reply_markup=reply_markup)
    elif data.startswith("remove_") and user_id == ADMIN_ID:
        ch = data.replace("remove_", "")
        remove_channel(ch)
        await query.edit_message_text(f"✅ تم إزالة القناة {ch}")
    elif data == "admin_show_channels" and user_id == ADMIN_ID:
        channels = get_all_channels()
        if channels:
            channels_text = "\n".join(channels)
            await query.edit_message_text(f"📌 القنوات المفروضة كشرط للاشتراك:\n{channels_text}")
        else:
            await query.edit_message_text("⚠️ لا توجد أي قناة مفروضة حالياً.")
    elif data == "admin_create_backup" and user_id == ADMIN_ID:
        backup_file = manual_backup()
        if backup_file:
            backup_name = os.path.basename(backup_file)
            await query.edit_message_text(f"✅ تم إنشاء نسخة احتياطية يدوية:\n{backup_name}")
        else:
            await query.edit_message_text("⚠️ فشل في إنشاء النسخة الاحتياطية.")
    elif data == "admin_restore_backup" and user_id == ADMIN_ID:
        backup_files = get_backup_files()
        if not backup_files:
            await query.edit_message_text("⚠️ لا توجد نسخ احتياطية متاحة للاستعادة.")
            return
        keyboard = [[InlineKeyboardButton(f"📄 {file}", callback_data=f"restore_{file}")] for file in backup_files]
        keyboard.append([InlineKeyboardButton("↩️ رجوع", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("اختر النسخة الاحتياطية التي تريد استعادتها:", reply_markup=reply_markup)
    elif data.startswith("restore_") and user_id == ADMIN_ID:
        backup_filename = data.replace("restore_", "")
        if restore_backup(backup_filename):
            await query.edit_message_text(f"✅ تم استعادة النسخة الاحتياطية:\n{backup_filename}\n\n⚠️ يُنصح بإعادة تشغيل البوت لضمان تحديث البيانات.")
        else:
            await query.edit_message_text("⚠️ فشلت استعادة النسخة الاحتياطية.")
    elif data == "back_to_main":
        await show_menu(update, context)
        context.user_data.pop("mode", None)

# ===== التعامل مع الرسائل =====
async def translate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    # التحقق من الاشتراك للمستخدم العادي
    if user_id != ADMIN_ID:
        unsubscribed = await get_unsubscribed_channels(update, context)
        if unsubscribed:
            channels_text = "\n".join(unsubscribed)
            await update.message.reply_text(
                f"⚠️ يجب الاشتراك في جميع القنوات التالية للحصول على الخدمة:\n{channels_text}"
            )
            return

    mode = context.user_data.get("mode")

    # إضافة قناة جديدة
    if mode == "add_channel" and user_id == ADMIN_ID:
        if not text.startswith("@"):
            await update.message.reply_text("⚠️ يجب أن يبدأ اسم القناة بـ @")
            return
        add_channel(text)
        await update.message.reply_text(f"✅ تم إضافة القناة {text} كشرط اشتراك.")
        context.user_data.pop("mode", None)
        return

    # البث الجماعي
    if mode == "broadcast" and user_id == ADMIN_ID:
        users = get_all_users()
        count = 0
        for u in users:
            if u == ADMIN_ID:
                continue
            try:
                await context.bot.send_message(chat_id=u, text=text)
                count += 1
            except:
                continue
        await update.message.reply_text(f"✅ تم إرسال الرسالة إلى {count} مستخدم/مشترك.")
        context.user_data.pop("mode", None)
        return

    # الترجمة العادية
    src_lang = "ar" if any("\u0600" <= ch <= "\u06FF" for ch in text) else "en"
    target = choose_target_lang(src_lang)
    try:
        translated = GoogleTranslator(source="auto", target=target).translate(text)
    except:
        await update.message.reply_text("⚠️ حدث خطأ أثناء الترجمة.")
        return
    await update.message.reply_text(f"🔄 الترجمة ({target}):\n{translated}")

# ===== الرئيسي =====
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_handler))

    print("✅ البوت شغال...")
    app.run_polling()

if __name__ == "__main__":
    main()