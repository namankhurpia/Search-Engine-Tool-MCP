FROM python:3.10-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Copy remaining files
COPY .env.example .env.example
COPY run.py .

# Create keys.csv if it doesn't exist (will be overwritten by volume mount)
RUN touch keys.csv

EXPOSE 8000

CMD ["uvicorn", "insight.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
