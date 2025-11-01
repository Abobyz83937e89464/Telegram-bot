# [REAL]
FROM python:3.10-slim

# Установка зависимостей
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY . .

# Команда запуска фонового процесса
CMD ["python3", "autoresponder.py"]
