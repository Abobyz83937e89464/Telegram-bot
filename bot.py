import os
import logging
import re
import sqlite3
import requests
import threading
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

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

conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

MAIN_MENU, PASSWORD_CHECK, SEARCH_QUERY, ADMIN_PANEL = range(4)

DRIVE_FILES = [
    {"name": "boo.wf_100mln_0.csv", "url": "https://drive.google.com/uc?export=download&id=1U6C-SqeNWv3ylYujFBTZS0yY1uWk2BQk"},
    {"name": "Clients.csv", "url": "https://drive.google.com/uc?export=download&id=1EicBhkkAOk_s27-_tHZnbAv8Ik_56TR3"},
    # ... остальные файлы
]

# ПУЛ ПОТОКОВ ДЛЯ МНОГОПОЛЬЗОВАТЕЛЬСКОСТИ
search_executor = ThreadPoolExecutor(max_workers=20)  # 20 одновременных поисков

async def save_user(user_id, username, first_name):
    try:
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", 
                 (user_id, username, first_name))
        conn.commit()
    except:
        pass

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
            logger.info(f"✅ {file_name} загружен")
    
    DATABASE_CACHE = new_cache
    CACHE_TIMESTAMP = current_time
    logger.info("✅ Все базы загружены в кэш")
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
        await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return MAIN_MENU
    else:
        await update.message.reply_text("🔐 **СИСТЕМА ПОИСКА**\n\nВведите пароль:")
        return PASSWORD_CHECK

# ... остальные функции (back_command, handle_main_menu, handle_admin_panel, check_password) остаются без изменений ...

async def search_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    
    if query == "/back":
        return await back_command(update, context)
    
    if len(query) < 2:
        await update.message.reply_text("❌ Минимум 2 символа")
        return SEARCH_QUERY
    
    search_message = await update.message.reply_text(f"🔍 **Поиск:** `{query}`\n\n*Сканирую 16 баз...*")
    
    # ЗАГРУЖАЕМ БАЗЫ В КЭШ
    databases = load_databases_to_cache()
    
    # БЫСТРЫЙ ПОИСК В КЭШЕ
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(search_executor, fast_search_in_cache, query, databases)
    
    await search_message.delete()
    
    if results:
        unique_results = list(set(results))[:100]  # Лимит 100 результатов
        response = f"✅ **НАЙДЕНО:** `{query}`\n\n📊 Результатов: {len(unique_results)}\n\n"
        
        for result in unique_results[:30]:  # Показываем первые 30
            response += f"• {result}\n"
        
        if len(unique_results) > 30:
            response += f"\n... и еще {len(unique_results) - 30} результатов"
            
        await update.message.reply_text(response)
    else:
        await update.message.reply_text(f"❌ **НЕ НАЙДЕНО:** `{query}`")
    
    await update.message.reply_text("**Введите данные для поиска или /back:**")
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
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("back", back_command)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("back", back_command))
    
    # ПРЕДЗАГРУЗКА БАЗ ПРИ СТАРТЕ
    if os.getenv('RENDER'):
        health_thread = threading.Thread(target=start_health_server, daemon=True)
        health_thread.start()
        logger.info("🔄 Предзагрузка баз в кэш...")
        load_databases_to_cache()
    
    logger.info("🟢 БОТ ЗАПУЩЕН! 50+ ПОЛЬЗОВАТЕЛЕЙ ГОТОВО!")
    app.run_polling()

if __name__ == "__main__":
    main()
