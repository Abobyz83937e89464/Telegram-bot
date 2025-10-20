import os
import logging
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "7736863012:AAEPt0by9-l9axEQq2oPzm_0dKfRdqte6Qg")
USER_PASSWORD = "morpa"
ADMIN_ID = 8049083248

logging.basicConfig(level=logging.INFO)

BASE_DIR = "base"
os.makedirs(BASE_DIR, exist_ok=True)

MAIN_MENU, PASSWORD_CHECK, SEARCH_QUERY, ADMIN_PANEL = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if user.id == ADMIN_ID:
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**\nВыберите режим:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return MAIN_MENU
    else:
        await update.message.reply_text("🔐 **СИСТЕМА ПОИСКА**\n\n💎 *Если информация существует - я её найду!*\n\nВведите пароль:")
        return PASSWORD_CHECK

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "🔍 Поиск данных":
        await update.message.reply_text("Введите пароль:", reply_markup=ReplyKeyboardRemove())
        return PASSWORD_CHECK
    elif choice == "👑 Админ панель":
        keyboard = [["📊 Статистика", "👥 Пользователи"], ["🔙 Назад"]]
        await update.message.reply_text("👑 **АДМИН ПАНЕЛЬ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return ADMIN_PANEL

async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "📊 Статистика":
        files = len(os.listdir(BASE_DIR)) if os.path.exists(BASE_DIR) else 0
        await update.message.reply_text(f"📊 **СТАТИСТИКА**\n\n📁 Файлов в базе: {files}")
        return ADMIN_PANEL
    elif choice == "🔙 Назад":
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return MAIN_MENU

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() != USER_PASSWORD:
        await update.message.reply_text("❌ НЕВЕРНЫЙ ПАРОЛЬ!")
        return ConversationHandler.END
    await update.message.reply_text("✅ ДОСТУП РАЗРЕШЕН!\n\nВведите данные для поиска:")
    return SEARCH_QUERY

async def search_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("❌ Минимум 2 символа")
        return SEARCH_QUERY
    
    await update.message.reply_text(f"🔍 **Поиск:** `{query}`\n\nСканирую базы...")
    results = []
    
    try:
        for filename in os.listdir(BASE_DIR):
            filepath = os.path.join(BASE_DIR, filename)
            if os.path.isfile(filepath):
                with open(filepath, "r", encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if query in line:
                            phone = re.findall(r'\d{7,15}', line)
                            name = re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', line)
                            if phone or name:
                                result = ""
                                if phone: result += f"📞 {phone[0]} "
                                if name: result += f"👤 {name[0]}"
                                results.append(result.strip())
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    
    if results:
        response = f"✅ **НАЙДЕНО:** {len(results)} записей\n\n" + "\n".join(results[:10])
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("❌ Ничего не найдено")
    
    await update.message.reply_text("Введите данные для поиска:")
    return SEARCH_QUERY

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
            PASSWORD_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_data)],
            ADMIN_PANEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_panel)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: u.message.reply_text("Отменено"))]
    )
    app.add_handler(conv_handler)
    logging.info("🟢 БОТ ЗАПУЩЕН!")
    app.run_polling()

if __name__ == "__main__":
    main()
