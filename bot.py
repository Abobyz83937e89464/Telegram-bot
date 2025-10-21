import os
import logging
import re
import requests
import asyncio
import time
import sys
from concurrent.futures import ThreadPoolExecutor
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

# ХРАНИЛИЩЕ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ И ЗАПРОСОВ
user_data = {}
active_searches = 0
max_concurrent_searches = 15  # УВЕЛИЧИЛИ ДО 15

MAIN_MENU, PASSWORD_CHECK, SEARCH_QUERY, ADMIN_PANEL, BROADCAST_MESSAGE, ADD_SEARCHES = range(6)

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

# ПУЛ ДЛЯ ПОИСКА - УВЕЛИЧИЛИ ДО 20 ПОТОКОВ
search_executor = ThreadPoolExecutor(max_workers=20)

def init_user(user_id):
    """ИНИЦИАЛИЗАЦИЯ ПОЛЬЗОВАТЕЛЯ"""
    if user_id not in user_data:
        user_data[user_id] = {
            "searches_left": 3,
            "last_reset": time.time(),
            "unlimited": False
        }
    elif user_id == ADMIN_ID:
        user_data[user_id]["unlimited"] = True
    
    # ПРОВЕРКА СБРОСА ЗАПРОСОВ (КАЖДЫЙ ЧАС)
    user = user_data[user_id]
    if time.time() - user["last_reset"] >= 3600:
        user["searches_left"] = 3
        user["last_reset"] = time.time()
    
    return user_data[user_id]

async def save_user(user_id, username, first_name):
    init_user(user_id)

def download_file_fast(drive_url, file_name):
    try:
        response = requests.get(drive_url, timeout=30)
        if response.status_code == 200:
            return response.text
        return ""
    except Exception as e:
        logger.error(f"Ошибка загрузки {file_name}: {e}")
        return ""

def search_in_file_sync(file_info, query):
    """СИНХРОННЫЙ ПОИСК В 1 ФАЙЛЕ"""
    try:
        content = download_file_fast(file_info["url"], file_info["name"])
        if not content:
            return []
        
        results = []
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
        
        return results
    except Exception as e:
        logger.error(f"Ошибка в базе {file_info['name']}: {e}")
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await save_user(user.id, user.username, user.first_name)
    user_info = init_user(user.id)
    
    if user.id == ADMIN_ID:
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text(
            f"🤖 **ГЛАВНОЕ МЕНЮ**\n\n💎 Запросов: ∞ (админ)\nВыберите режим:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            f"🔐 **СИСТЕМА ПОИСКА**\n\n"
            f"💎 *Доступно запросов: {user_info['searches_left']}/3*\n"
            f"🕐 *Пополнение: каждые 60 минут*\n\n"
            f"💎 *Если информация существует - я её найду!*\n\n"
            f"Введите пароль:"
        )
        return PASSWORD_CHECK

async def back_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_info = init_user(user.id)
    
    if user.id == ADMIN_ID:
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text(
            f"🤖 **ГЛАВНОЕ МЕНЮ**\n\n💎 Запросов: ∞ (админ)\nВыберите режим:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            f"🔐 **СИСТЕМА ПОИСКА**\n\n"
            f"💎 *Доступно запросов: {user_info['searches_left']}/3*\n"
            f"🕐 *Пополнение: каждые 60 минут*\n\n"
            f"💎 *Если информация существует - я её найду!*\n\n"
            f"Введите пароль:"
        )
        return PASSWORD_CHECK

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_info = init_user(user.id)
    
    choice = update.message.text
    
    if choice == "🔍 Поиск данных":
        await update.message.reply_text("Введите пароль:", reply_markup=ReplyKeyboardRemove())
        return PASSWORD_CHECK
        
    elif choice == "👑 Админ панель":
        keyboard = [
            ["📊 Статистика", "👥 Пользователи"],
            ["🎁 Выдать запросы", "📢 Рассылка"],
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
        total_users = len(user_data)
        active_now = sum(1 for user_id in user_data if time.time() - user_data[user_id].get("last_reset", 0) < 86400)
        await update.message.reply_text(
            f"📊 **СТАТИСТИКА**\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"🔥 Активных (24ч): {active_now}\n"
            f"📁 Файлов: {len(DRIVE_FILES)}\n"
            f"🔍 Активных поисков: {active_searches}"
        )
        return ADMIN_PANEL
        
    elif choice == "👥 Пользователи":
        recent_users = sorted(user_data.items(), key=lambda x: x[1].get("last_reset", 0), reverse=True)[:5]
        response = "👥 **ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ:**\n\n"
        for user_id, data in recent_users:
            searches = data.get("searches_left", 0)
            response += f"👤 ID: {user_id}\n💎 Запросов: {searches}\n━━━━━━━━━━\n"
        await update.message.reply_text(response)
        return ADMIN_PANEL
        
    elif choice == "🎁 Выдать запросы":
        await update.message.reply_text(
            "🎁 **ВЫДАЧА ЗАПРОСОВ**\n\n"
            "Введите ID пользователя и количество запросов через пробел:\n"
            "Пример: `123456789 10` - выдать 10 запросов пользователю 123456789\n\n"
            "Или: `123456789 unlimited` - выдать безлимит",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_SEARCHES
        
    elif choice == "📢 Рассылка":
        await update.message.reply_text("📢 **РАССЫЛКА**\n\nВведите сообщение для рассылки:", reply_markup=ReplyKeyboardRemove())
        return BROADCAST_MESSAGE
        
    elif choice == "🔙 В главное меню":
        keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
        await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False))
        return MAIN_MENU

async def handle_add_searches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    
    if len(parts) != 2:
        await update.message.reply_text("❌ Неверный формат. Используйте: `ID_пользователя количество`")
        return ADD_SEARCHES
    
    try:
        user_id = int(parts[0])
        amount = parts[1]
        
        if user_id not in user_data:
            await update.message.reply_text("❌ Пользователь не найден")
            return ADD_SEARCHES
        
        if amount.lower() == "unlimited":
            user_data[user_id]["unlimited"] = True
            user_data[user_id]["searches_left"] = 9999
            await update.message.reply_text(f"✅ Пользователю {user_id} выдан БЕЗЛИМИТ")
        else:
            add_amount = int(amount)
            user_data[user_id]["searches_left"] += add_amount
            await update.message.reply_text(f"✅ Пользователю {user_id} добавлено {add_amount} запросов")
        
        # ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ ПОЛЬЗОВАТЕЛЮ
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎁 **Вам выданы дополнительные запросы!**\n\n"
                     f"💎 Теперь доступно: {user_data[user_id]['searches_left']} запросов\n\n"
                     f"Спасибо за использование нашего сервиса! 💫"
            )
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: `ID_пользователя количество`")
        return ADD_SEARCHES
    
    keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
    await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False))
    return MAIN_MENU

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    success = 0
    failed = 0
    
    broadcast_msg = await update.message.reply_text(f"📢 **Рассылка начата**\n\nОтправлено: 0/{len(user_data)}")
    
    for user_id in list(user_data.keys()):
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 **РАССЫЛКА:**\n\n{message}")
            success += 1
            if success % 10 == 0:
                await broadcast_msg.edit_text(f"📢 **Рассылка...**\n\nОтправлено: {success}/{len(user_data)}")
        except:
            failed += 1
    
    await broadcast_msg.edit_text(f"✅ **Рассылка завершена**\n\n✅ Успешно: {success}\n❌ Не удалось: {failed}")
    
    keyboard = [["🔍 Поиск данных", "👑 Админ панель"]]
    await update.message.reply_text("🤖 **ГЛАВНОЕ МЕНЮ**", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False))
    return MAIN_MENU

async def check_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_info = init_user(user.id)
    
    if update.message.text.strip() != USER_PASSWORD:
        await update.message.reply_text("❌ НЕВЕРНЫЙ ПАРОЛЬ!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"✅ ДОСТУП РАЗРЕШЕН!\n\n"
        f"💎 *Доступно запросов: {user_info['searches_left']}/3*\n\n"
        f"Введите данные для поиска:"
    )
    return SEARCH_QUERY

async def search_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_searches
    
    user = update.message.from_user
    user_info = init_user(user.id)
    
    # ПРОВЕРКА ЗАПРОСОВ
    if not user_info["unlimited"] and user_info["searches_left"] <= 0:
        await update.message.reply_text(
            "❌ **ЗАПРОСЫ ЗАКОНЧИЛИСЬ!**\n\n"
            "💎 Все 3 поиска израсходованы\n"
            "🕐 Новые запросы будут через 60 минут\n\n"
            "🚀 **ХОТИТЕ БОЛЬШЕ ЗАПРОСОВ?**\n"
            "Обратитесь к создателю: @the_observer_os\n\n"
            "💫 *Мы ценим каждого пользователя!*"
        )
        return ConversationHandler.END
    
    if active_searches >= max_concurrent_searches:
        await update.message.reply_text("⏳ Сервер перегружен. Попробуйте через 10 секунд.")
        return SEARCH_QUERY
    
    query = update.message.text.strip()
    
    if query == "/back":
        return await back_command(update, context)
    
    if len(query) < 2:
        await update.message.reply_text("❌ Минимум 2 символа")
        return SEARCH_QUERY
    
    # СПИСЫВАЕМ ЗАПРОС
    if not user_info["unlimited"]:
        user_info["searches_left"] -= 1
    
    active_searches += 1
    searches_left = user_info["searches_left"] if not user_info["unlimited"] else "∞"
    
    search_message = await update.message.reply_text(
        f"🔍 **Поиск:** `{query}`\n\n"
        f"💎 *Осталось запросов: {searches_left}*\n"
        f"*Сканирую 16 баз... (1-2 минуты)*"
    )
    
    try:
        # ЗАПУСКАЕМ ПОИСК В ОТДЕЛЬНОМ ПОТОКЕ СРАЗУ
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(search_executor, perform_search, query)
        
        # ЖДЕМ РЕЗУЛЬТАТ АСИНХРОННО - БОТ НЕ БЛОКИРУЕТСЯ
        results = await asyncio.wait_for(future, timeout=120.0)  # 2 минуты таймаут
        
        await search_message.delete()
        
        if results:
            unique_results = list(set(results))
            response = (
                f"✅ **НАЙДЕНО:** `{query}`\n\n"
                f"📊 Найдено: {len(unique_results)}\n"
                f"💎 Осталось запросов: {searches_left}\n\n"
            )
            
            for result in unique_results[:30]:
                response += f"• {result}\n"
                
            if len(unique_results) > 30:
                response += f"\n... и еще {len(unique_results) - 30} результатов"
                
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(
                f"❌ **НЕ НАЙДЕНО:** `{query}`\n\n"
                f"💎 Осталось запросов: {searches_left}"
            )
        
        if not user_info["unlimited"] and user_info["searches_left"] == 0:
            await update.message.reply_text(
                "⚠️ **ПОСЛЕДНИЙ ЗАПРОС ИСПОЛЬЗОВАН!**\n\n"
                "🚀 **ХОТИТЕ БОЛЬШЕ ЗАПРОСОВ?**\n"
                "Обратитесь к создателю: @the_observer_os\n\n"
                "💫 *Мы ценим каждого пользователя!*"
            )
        
        await update.message.reply_text("**Введите данные для поиска или /back:**")
        
    except asyncio.TimeoutError:
        await search_message.edit_text("⏰ Поиск прерван (таймаут 2 минуты)")
        await update.message.reply_text("**Введите данные для поиска или /back:**")
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        await search_message.edit_text("❌ Ошибка поиска")
        await update.message.reply_text("**Введите данные для поиска или /back:**")
    finally:
        active_searches -= 1
    
    return SEARCH_QUERY

def perform_search(query):
    """СИНХРОННАЯ ФУНКЦИЯ ПОИСКА В ОТДЕЛЬНОМ ПОТОКЕ"""
    results = []
    
    for i, file_info in enumerate(DRIVE_FILES):
        try:
            content = download_file_fast(file_info["url"], file_info["name"])
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
            logger.error(f"Ошибка в базе {file_info['name']}: {e}")
            continue
    
    return results

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
            ADD_SEARCHES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_searches)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("back", back_command)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("back", back_command))
    
    # АДМИНУ БЕЗЛИМИТ
    init_user(ADMIN_ID)
    user_data[ADMIN_ID]["unlimited"] = True
    user_data[ADMIN_ID]["searches_left"] = 9999
    
    logging.info(f"🟢 БОТ ЗАПУЩЕН! 15+ пользователей одновременно!")
    app.run_polling()

if __name__ == "__main__":
    main()
