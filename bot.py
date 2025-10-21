import os
import logging
import re
import sqlite3
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
BOT_TOKEN = os.getenv('BOT_TOKEN')
USER_PASSWORD = "morpa"
ADMIN_ID = 8049083248

logging.basicConfig(level=logging.INFO)

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

async def save_user(user_id, username, first_name):
    try:
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)", 
                 (user_id, username, first_name))
        conn.commit()
    except:
        pass

def download_file_fast(drive_url, file_name):
    try:
        response = requests.get(drive_url, timeout=60)
        if response.status_code == 200:
            logging.info(f"✅ Скачан {file_name}")
            return response.text
        logging.error(f"❌ Ошибка скачивания {file_name}: {response.status_code}")
        return ""
    except Exception as e:
        logging.error(f"❌ Ошибка {file_name}: {e}")
        return ""

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
            ["🔙 В главное меню"]
        ]
        await update.message.reply_text(
            "👑 **АДМИН ПАНЕЛЬ**\nВыберите действие:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return ADMIN_PANEL

async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    
    if choice == "📊 Статистика":
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        files_count = len(DRIVE_FILES)
        await update.message.reply_text(f"📊 **СТАТИСТИКА**\n\n👥 Пользователей: {user_count}\n📁 Файлов: {files_count}")
        return ADMIN_PANEL
        
    elif choice == "👥 Пользователи":
        c.execute("SELECT user_id, first_name, joined_date FROM users ORDER BY joined_date DESC LIMIT 5")
        users = c.fetchall()
        response = "👥 **ПОЛЬЗОВАТЕЛИ:**\n\n"
        for user in users:
            response += f"👤 {user[1] or 'No name'}\n🆔 {user[0]}\n📅 {user[2]}\n━━━━━━━━━━\n"
        await update.message.reply_text(response)
        return ADMIN_PANEL
        
    elif choice == "🔙 В главное меню":
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
    query = update.message.text.strip()
    
    if query == "/back":
        return await back_command(update, context)
    
    if len(query) < 2:
        await update.message.reply_text("❌ Минимум 2 символа")
        return SEARCH_QUERY
    
    search_message = await update.message.reply_text(f"🔍 **Поиск:** `{query}`\n\n*Сканирую 16 баз...*")
    
    results = []
    files_searched = 0
    
    try:
        for file_info in DRIVE_FILES:
            files_searched += 1
            await search_message.edit_text(f"🔍 **Поиск:** `{query}`\n\n*Проверено {files_searched}/16 файлов...*")
            
            file_name = file_info["name"]
            file_url = file_info["url"]
            
            content = download_file_fast(file_url, file_name)
            
            if content:
                for line in content.splitlines():
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
                    
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    
    await search_message.delete()
    
    if results:
        unique_results = list(set(results))
        response = f"✅ **НАЙДЕНО:** `{query}`\n\n"
        response += f"📊 Найдено: {len(unique_results)}\n\n"
        
        for result in unique_results[:50]:
            response += f"• {result}\n"
            
        await update.message.reply_text(response)
    else:
        await update.message.reply_text(f"❌ **НЕ НАЙДЕНО:** `{query}`\n\nПроверено файлов: {files_searched}/16")
    
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
    
    if os.getenv('RENDER'):
        health_thread = threading.Thread(target=start_health_server, daemon=True)
        health_thread.start()
    
    logging.info("🟢 БОТ ЗАПУЩЕН! 16 БАЗ ГОТОВЫ!")
    app.run_polling()

if __name__ == "__main__":
    main()
