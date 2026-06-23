# Use the official optimized Python slim environment
FROM python:3.14-slim

# Install system-level dependencies required for building wheels and network auth
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set standard working boundary inside the container
WORKDIR /app

# Ensure logs flow directly to Google Cloud Logging without buffering delay
ENV PYTHONUNBUFFERED=1

# Copy package requirements separately to optimize Docker layer caching
COPY requirements.txt .

#COPY neo_api_client /app/neo_api_client

# Install production dependencies
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt 
# ./neo_api_client

# Copy all project strategy assets and modular files
COPY . .

# Expose port 8080 documentation-wise
EXPOSE 8080

# Ensure it uses intuitive:app instead of main:app
CMD ["uvicorn", "intuitive:app", "--host", "0.0.0.0", "--port", "8080"]