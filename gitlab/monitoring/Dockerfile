FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gitlab_exporter.py .
COPY config.py .

EXPOSE 9200

CMD ["python", "gitlab_exporter.py"]
