
# Multi-stage build for smaller, more secure images
FROM python:3.9-slim as builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y ffmpeg libsndfile1 build-essential && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Final image
FROM python:3.9-slim
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y ffmpeg libsndfile1 && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages and app from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY --from=builder /app /app

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
