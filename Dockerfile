# Chhota python image
FROM python:3.10-slim
# Python ke logs foran dikhein
ENV PYTHONUNBUFFERED=1
# Kaam karne ka folder
WORKDIR /app
# Pehle sirf requirements copy karo (build cache ke liye)
COPY requirements.txt .
# Libraries install karo
RUN pip install --no-cache-dir -r requirements.txt
# Phir poora code copy karo
COPY . .
# Root user se bachne ke liye normal user banao
RUN useradd -m appuser && mkdir -p /data && chown -R appuser /app /data
# Ab normal user se chalao
USER appuser
# Database ki jagah
ENV DB_PATH=/data/trade_desk.db
# App ka port
EXPOSE 8000
# Server chalao (PORT platform deta hai, warna 8000)
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
