FROM python:3.9-slim

WORKDIR /app

# System dependencies install
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project files copy
COPY . .

# Default command
CMD ["python", "src/main.py"]
