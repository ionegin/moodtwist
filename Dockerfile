# Используем легковесный образ Python
FROM python:3.11-slim

# Ожидает порт 7860
EXPOSE 7860

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Запускает контейнер от UID 1000
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Отладочная информация
RUN echo "=== DOCKER DEBUG ===" && ls -la /app && echo "=== APP.PY CONTENT ===" && head -5 /app/app.py && echo "=================="

# Минимальный тестовый запуск
ENTRYPOINT ["sh", "-c", "echo '🔥 ENTRYPOINT = APP' 1>&2; exec python -u app.py"]
