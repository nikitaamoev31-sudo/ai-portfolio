# Используем официальный легковесный образ Python
FROM python:3.12-slim

# Устанавливаем системные зависимости для работы браузера
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую папку в контейнере
WORKDIR /app

# Сначала копируем зависимости и ставим их (для кэширования слоев Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Специфический шаг для crawl4ai: ставим playwright и его системные библиотеки
RUN python -m playwright install --with-deps chromium

# Копируем весь остальной код агента
COPY . .
COPY system_prompt.txt .

# Запуск главного скрипта (если у тебя другое имя, замени ai_lead_generation.py)
CMD ["python", "ai_lead_generation.py"]
