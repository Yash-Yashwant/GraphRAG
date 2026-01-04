# 1. Start with your base
FROM python:3.10-slim

# 2. Install system-level tools (rarely change)
RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. CRITICAL: Copy ONLY requirements.txt first
# This creates a "Dependency Layer"
COPY requirements.txt .

# 4. Install the heavy libraries (marker-pdf, grobid-client)
# As long as requirements.txt doesn't change, this is cached forever
RUN pip install --no-cache-dir -r requirements.txt

# 5. LAST STEP: Copy your actual code
# Since your code changes often, this layer will rebuild, 
# but it will start FROM the already-installed dependencies above.
COPY . .

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
