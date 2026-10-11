FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY api /app/api
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
