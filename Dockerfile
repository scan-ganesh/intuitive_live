# Use official Python runtime
FROM python:3.14.2-slim

# Set working folder inside container
WORKDIR /app


# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy ALL project files (your script + utils + csv)
COPY . .

# Run your main script when job executes
CMD ["python", "intuitive.py"]
