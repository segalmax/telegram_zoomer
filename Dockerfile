FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot.py translator.py image_generator.py ./

# Create directories for logs and sessions
RUN mkdir -p /app/logs /app/session

# Define volumes
VOLUME /app/session
VOLUME /app/logs

CMD ["python", "bot.py"] 