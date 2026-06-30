# Use Python 3.10 slim base image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies (if any are needed, e.g. curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application directories
COPY .agents/ .agents/
COPY agentic_workflow/ agentic_workflow/
COPY web_app/ web_app/
COPY weather_mcp.py .

# Expose port
EXPOSE 8080

# Start Uvicorn FastAPI server
CMD ["uvicorn", "web_app.main:app", "--host", "0.0.0.0", "--port", "8080"]
