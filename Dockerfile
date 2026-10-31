# ---- Stage 1: build React frontend ----
FROM node:20-slim AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: FastAPI + Faster-Whisper ----
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 WHISPER_MODEL=tiny
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Bake the speech model into the image so cold starts don't download it
RUN python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8')"
COPY backend/app ./app
COPY --from=fe /fe/dist ./frontend_dist
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --ws-ping-interval 30 --ws-ping-timeout 120"]
