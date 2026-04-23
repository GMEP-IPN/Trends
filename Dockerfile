FROM python:3.12-slim

# libsnap7 для Siemens S7
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsnap7-1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости (отдельным слоем для кэширования)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    sqlalchemy \
    python-snap7 \
    pycomm3 \
    fastapi \
    uvicorn \
    pydantic \
    pyyaml

COPY . .

RUN mkdir -p DB logs

EXPOSE 8000

ENV TRENDS_HOST=0.0.0.0

CMD ["python", "run.py"]
