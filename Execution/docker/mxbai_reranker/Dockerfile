FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/hf \
    TRANSFORMERS_CACHE=/data/hf/hub \
    MODEL_ID=mixedbread-ai/mxbai-rerank-base-v2 \
    MODEL_CACHE_DIR=/data/hf \
    PORT=8000

WORKDIR /app

RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.5.1 && \
    pip install --no-cache-dir \
    fastapi==0.115.12 \
    "uvicorn[standard]==0.34.0" \
    "transformers>=4.49.0,<5.0.0" \
    mxbai-rerank

COPY app.py /app/app.py

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
