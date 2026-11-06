FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor.py watchlist.json ./
ENV POLL_SECONDS=120 EMAIL_ENABLED=false DATA_DIR=/data
CMD ["python", "-u", "monitor.py"]
