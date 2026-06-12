# Use official Python runtime
FROM python:3.14.2-slim

# Set working folder inside container
WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL project files (your script + utils + csv)
COPY . .

# Expose port 8080 documentation-wise (Cloud Run overrides this via env vars, but good for local)
EXPOSE 8080

# Run your main script when job executes
CMD ["python", "intuitive.py"]
