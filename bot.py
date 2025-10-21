import os
import logging
import re
import requests
import threading
import asyncio
import time
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ФИКС ДЛЯ IMGHDR
if sys.version_info >= (3, 11):
    import imghdr
else:
    class imghdr:
        @staticmethod
        def what(file, h=None):
            return None

BOT_TOKEN = os.getenv('BOT_TOKEN')
USER_PASSWORD = "morpa"
ADMIN_ID = 8049083248

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# КЭШ БАЗ ДАННЫХ В ОЗУ
DATABASE_CACHE = {}
CACHE_TIMESTAMP = 0
CACHE_TTL = 3600  # 1 час

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(('0.0.0.0', 10000), HealthHandler)
    server.serve_forever()

# ХРАНИЛИЩЕ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ И РАССЫЛКИ
user_ids = set()
active_searches = 0
max_concurrent_searches = 10

MAIN_MENU, PASSWORD_CHECK, SEARCH_QUERY, ADMIN_PANEL, BROADCAST_MESSAGE = range(5)

DRIVE_FILES = [
    {"name": "boo.wf_100mln_0.csv", "url": "https://drive.google.com/uc?export=download&id=1U6C-SqeNWv3ylYujFBTZS0yY1uWk2BQk"},
    {"name": "Clients.csv", "url": "https://drive.google.com/uc?export=download&id=1EicBhkkAOk_s27-_tHZnbAv8Ik_56TR3"},
    {"name": "emails1.csv", "url": "https://drive.google.com/uc?export=download&id=1LH8xf06jH7GnOGCC92Ld7e5hJpN4ZxAV"},
    {"name": "enter_data_copy.sql", "url": "https://drive.google.com/uc?export=download&id=1IDEEjS3gE4TsqJ-_bdYPAfttS7Slbyq2"},
    {"name": "Fbi.gov.csv", "url": "https://drive.google.com/uc?export=download&id=1leVbmb7ZHOw5f9NBLEImu2Ob2UPLiKlk"},
    {"name": "GetContact_2020_19kk.csv", "url": "https://drive.google.com/uc?export=download&id=1f0Ns-HJfZQyn-5SBj74QTUwBvHW9n6yh"},
    {"name": "getcontact.com numbuster.com.csv", "url": "https://drive.google.com/uc?export=download&id=1czMpRLgFXQo8xTs6FDZVL7_jFF99Xpar"},
    {"name": "getcontact.csv", "url": "https://drive.google.com/uc?export=download&id=1gSCz1BnD1M19hZpQow_-3s8CnVhm8RxQ"},
    {"name": "hlbd_form_results.sql", "url": "https://drive.google.com/uc?export=download&id=1hCEPyENccz0m4qKlvrMJVCj_Y0IcH9j_"},
    {"name": "itlyceum_felix.csv", "url": "https://drive.google.com/uc?export=download&id=1oBzfT6JOxJkYajCBA9iXvg6Jc_KSZwfK"},
    {"name": "kztg.csv", "url": "https://drive.google.com/uc?export=download&id=1SlTbBKJ-BDoEpyyL0L46c45Bu142H4pM"},
    {"name": "Phone Pay -1.xlsx", "url": "https://drive.google.com/uc?export=download&id=1k3R1TxqoeTMvguYn8pjCICNFcU7mup2l"},
    {"name": "Phone Pay -2.xlsx", "url": "https://drive.google.com/uc?export=download&id=1k3R1TxqoeTMvguYn8pjCICNFcU7mup2l"},
    {"name": "Phone Pay.xlsx", "url": "https://drive.google.com/uc?export=download&id=1vMylLEXUECkL5rvXVgeKejDA_RiFyfOt"},
    {"name": "phone.csv", "url": "https://drive.google.com/uc?export=download&id=1_4fy0XswInx6Ke8JzI0gKuo5jzcG4LYm"},
    {"name": "Адрес клиентов_9.3k.csv", "url": "https://drive.google.com/uc?export=download&id=1nZIuSMThLynwXkrJj6jWgos-NwvsSrps"}
]

# ПУЛ ДЛЯ ПОИСКА
search_executor = ThreadPoolExecutor(max_workers=15)

async def save_user(user_id, username, first_name):
    user_ids.add(user_id)

def download_file_fast(drive_url, file_name):
    try:
        response = requests.get(drive_url, timeout=30)
        if response.status_code == 200:
            return response.text
        return ""
    except:
        return ""

def load_databases_to_cache():
    """ЗАГРУЖАЕМ БАЗЫ В КЭШ 1 РАЗ В ЧАС"""
    global DATABASE_CACHE, CACHE_TIMESTAMP
    
    current_time = time.time()
    if current_time - CACHE_TIMESTAMP < CACHE_TTL and DATABASE_CACHE:
        return DATABASE_CACHE
    
    logger.info("🔄 Загрузка баз в кэш...")
    new_cache = {}
    
    for file_info in DRIVE_FILES:
        file_name = file_info["name"]
        file_url = file_info["url"]
        
        content = download_file_fast(file_url, file_name)
        if content:
            new_cache[file_name] = content.splitlines()
    
    DATABASE_CACHE = new_cache
    CACHE_TIMESTAMP = current_time
    logger.info(f"✅ Базы загружены: {len(DATABASE_CACHE)} файлов")
    return DATABASE_CACHE

def fast_search_in_cache(query, databases):
    """БЫСТРЫЙ ПОИСК В КЭШИРОВАННЫХ БАЗАХ"""
    results = []
    
    for file_name, lines in databases.items():
        for line in lines:
            if query in line:
                phones = re.findall(r'\d{7,15}', line)
                names = re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', line)
                emails = re.findall(r'\S+@\S+', line)
                
                for phone in phones:
                    results.append(f"📞 {phone}")
                for name in names:
                    results.append(f"👤 {name}")
                for email in emails:
                    results.append(f"📧 {email}")
    
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await save_user(user.id, user.username, user.first_name)
    
    if user.id == ADMIN_ID:
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text(
            "🤖 **ГЛАВНОЕ МЕНЮ**\nВыберите режим:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "🔐 **СИСТЕМА ПОИСКА**\n\n💎 *Если информация существует - я её найду!*\n\nВведите пароль:"
        )
        return PASSWORD_CHECK

async def back_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if user.id == ADMIN_ID:
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text(
            "🤖 **ГЛАВНОЕ МЕНЮ**\nВыберите режим:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "🔐 **СИСТЕМА ПОИСКА**\n\n💎 *Если информация существует - я её найду!*\n\nВведите пароль:"
        )
        return PASSWORD_CHECK

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    if choice == "🔍 Поиск данных":
        await update.message.reply_text("Введите пароль:", reply_markup=ReplyKeyboardRemove())
        return PASSWORD_CHECK
        
    elif choice == "👑 Админ панель":
        keyboard = [
            ["📊 Статистика", "👥 Пользователи"],
            ["📢 Рассылка", "🔙 В главное меню"]
        ]
        await update.message.reply_text(
            "👑 **АДМИН ПАНЕЛЬ**\nВыберите действие:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return ADMIN_PANEL

async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    if choice == "📊 Статистика":
        await update.message.reply_text(f"📊 **СТАТИСТИКА**\n\n👥 Пользователей: {len(user_ids)}\n📁 Файлов: {len(DRIVE_FILES)}\n🔍 Активных поисков: {active_searches}")
        return ADMIN_PANEL
        
    elif choice == "👥 Пользователи":
        await update.message.reply_text(f"👥 **ПОЛЬЗОВАТЕЛИ**\n\nВсего пользователей: {len(user_ids)}")
        return ADMIN_PANEL
        
    elif choice == "📢 Рассылка":
        await update.message.reply_text("📢 **РАССЫЛКА**\n\nВведите сообщение для рассылки:", reply_markup=ReplyKeyboardRemove())
        return BROADCAST_MESSAGE
        
    elif choice == "🔙 В главное меню":
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False))
        return MAIN_MENU

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    success = 0
    failed = 0
    
    broadcast_msg = await update.message.reply_text(f"📢 **Рассылка начата**\n\nОтправлено: 0/{len(user_ids)}")
    
    for user_id in list(user_ids):
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 **РАССЫЛКА:**\n\n{message}")
            success += 1
            if success % 10 == 0:
                await broadcast_msg.edit_text(f"📢 **Рассылка...**\n\nОтправлено: {success}/{len(user_ids)}")
        except:
            failed += 1
    
    await broadcast_msg.edit_text(f"✅ **Рассылка завершена**\n\n✅ Успешно: {success}\n❌ Не удалось: {failed}")
    
    keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
    await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False))
    return MAIN_MENU

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() != USER_PASSWORD:
        await update.message.reply_text("❌ НЕВЕРНЫЙ ПАРОЛЬ!")
        return ConversationHandler.END
    
    await update.message.reply_text("✅ ДОСТУП РАЗРЕШЕН!\n\nВведите данные для поиска:")
    return SEARCH_QUERY

async def search_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_searches
    
    # ПРОВЕРКА ЛИМИТА ПОИСКОВ
    if active_searches >= max_concurrent_searches:
        await update.message.reply_text("⏳ Сервер перегружен. Попробуйте через 10 секунд.")
        return SEARCH_QUERY
    
    query = update.message.text.strip()
    
    if query == "/back":
        return await back_command(update, context)
    
    if len(query) < 2:
        await update.message.reply_text("❌ Минимум 2 символа")
        return SEARCH_QUERY
    
    active_searches += 1
    search_message = await update.message.reply_text(f"🔍 **Поиск:** `{query}`\n\n*Сканирую 16 баз...*")
    
    try:
        # ЗАГРУЖАЕМ БАЗЫ В КЭШ
        databases = load_databases_to_cache()
        
        # БЫСТРЫЙ ПОИСК В КЭШЕ С ТАЙМАУТОМ
        loop = asyncio.get_event_loop()
        results = await asyncio.wait_for(
            loop.run_in_executor(search_executor, fast_search_in_cache, query, databases),
            timeout=15.0
        )
        
        await search_message.delete()
        
        if results:
            unique_results = list(set(results))[:50]
            response = f"✅ **НАЙДЕНО:** `{query}`\n\n📊 Найдено: {len(unique_results)}\n\n"
            
            for result in unique_results[:20]:
                response += f"• {result}\n"
                
            if len(unique_results) > 20:
                response += f"\n... и еще {len(unique_results) - 20} результатов"
                
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(f"❌ **НЕ НАЙДЕНО:** `{query}`")
        
        await update.message.reply_text("**Введите данные для поиска или /back:**")
        
    except asyncio.TimeoutError:
        await search_message.edit_text("⏰ Поиск прерван (таймаут 15с)")
        await update.message.reply_text("**Введите данные для поиска или /back:**")
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await search_message.edit_text("❌ Ошибка поиска")
        await update.message.reply_text("**Введите данные для поиска или /back:**")
    finally:
        active_searches -= 1
    
    return SEARCH_QUERY

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Отменено")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu)],
            PASSWORD_CHECK: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_data)],
            ADMIN_PANEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_panel)],
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("back", back_command)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("back", back_command))
    
    # ПРЕДЗАГРУЗКА БАЗ
    logger.info("🔄 Предзагрузка баз в кэш...")
    load_databases_to_cache()
    
    logging.info(f"🟢 БОТ ЗАПУЩЕН! {max_concurrent_searches} одновременных поисков!")
    app.run_polling()

if __name__ == "__main__":
    main()
