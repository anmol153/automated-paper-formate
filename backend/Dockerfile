FROM python:3.14-slim

RUN groupadd -r appuser && useradd -r -g appuser -m -s /sbin/nologin appuser
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
RUN mkdir -p data && chown -R appuser:appuser /app/backend
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
