FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Expose port (default 8080 for Cloud Run)
ENV PORT=8080
EXPOSE 8080

# Command to run the server
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
