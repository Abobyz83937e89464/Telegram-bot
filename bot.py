# [REAL] - Автоответчик EraFox: Встроенная Конфигурация с Новыми Ключами
import os
import asyncio
import logging
import random
import time
from telethon import TelegramClient, events

# === КОНФИГУРАЦИЯ ERAFOX: ВСТРОЕННЫЕ УЧЕТНЫЕ ДАННЫЕ (ОБНОВЛЕНО) ===
API_ID = 27565611
API_HASH = '5f7c8476ca146158fb1aff3ff8eb4f84'
PHONE = '+380998627460'  # <-- НОВЫЙ НОМЕР ТЕЛЕФОНА
PASSWORD = 'Пельмени' 

SESSION_NAME = 'er_twin_session' 

# КОНКРЕТНЫЙ ТЕКСТ АВТООТВЕТА
AUTO_REPLY_MESSAGE = (
    "Здравствуйте!\n"
    "Я сейчас занят, отвечу позже.\n"
    ".Автоответчик."
)

# [SIM] - Настройки для "живого" и безопасного ответа
REPLIED_USERS = {} 
COOLDOWN_SECONDS = 1800 # 30 минут. 
TYPING_DELAY_RANGE = (1, 3) # Имитация набора текста: от 1 до 3 секунд

# Настройка логирования
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.INFO)

# === ОСНОВНОЙ КОД ===
async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    logging.info("🔐 Запускаю авторизацию Telethon...")
    
    try:
        await client.start(phone=PHONE, password=PASSWORD)
    except Exception as e:
        logging.critical(f"❌ Критическая ошибка авторизации: {e}")
        return

    me = await client.get_me()
    logging.info(f"✅ Аккаунт @{me.username or me.first_name} авторизован!")
    print("📱 Автоответчик EraFox запущен. Ожидаю личные сообщения...")
    
    # ОБРАБОТЧИК АВТООТВЕТА: ТОЛЬКО ЛИЧНЫЕ ВХОДЯЩИЕ СООБЩЕНИЯ ОТ ЛЮДЕЙ
    @client.on(events.NewMessage(incoming=True, private=True))
    async def handle_auto_reply(event):
        sender = await event.get_sender()
        user_id = sender.id
        current_time = time.time()
        
        # 1. Исключаем ботов и самоответы
        if sender.bot or user_id == me.id:
            return
            
        # 2. Проверка на кулдаун (30 минут)
        if user_id in REPLIED_USERS and (current_time - REPLIED_USERS[user_id]) < COOLDOWN_SECONDS:
            logging.info(f"Пропущено: активен кулдаун для {sender.username or user_id}.")
            return

        logging.info(f"🔥 Входящее ЛС от: {sender.username or user_id}. Текст: '{event.text}'")

        # 3. [SIM] Имитация набора текста
        typing_delay = random.uniform(*TYPING_DELAY_RANGE)
        async with client.action(event.chat_id, 'typing'):
            await asyncio.sleep(typing_delay) 
            
        # 4. Отправка автоответа
        await event.reply(AUTO_REPLY_MESSAGE)
        
        REPLIED_USERS[user_id] = current_time
        logging.info(f"✅ Отправлен автоответ пользователю {sender.username or user_id}.")

    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
