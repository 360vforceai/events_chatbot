FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Run FastAPI + bot together via a process manager (or use separate containers)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
