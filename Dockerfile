FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default command: Run the replay engine
CMD ["python", "replay_engine.py", "--mode", "replay"]

