FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
# libgl1 - замена для libgl1-mesa-glx (нужен для OpenCV)
# libgomp1 - нужен для некоторых версий OpenVINO/ONNX Runtime
# libpq-dev - нужен для psycopg2
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Команда запуска переопределяется в docker-compose.yml
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]