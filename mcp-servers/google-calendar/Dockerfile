FROM python:3.11-slim

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==2.1.1

# Copy repository config
COPY pyproject.toml poetry.lock ./

# Copy the unibot_mcp_servers sources so poetry can install it as a package
COPY src ./src

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction --no-ansi

# Copy application code
COPY mcp-servers/google-calendar/main.py .

# Expose port (default 8080 for Cloud Run)
ENV PORT=8080
EXPOSE 8080

# Command to run the server
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
