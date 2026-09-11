FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common library
COPY libs/common /app/libs/common
RUN pip install -e /app/libs/common

COPY services/content-automation/generator/app /app/app
COPY brand-voice /app/brand-voice

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

