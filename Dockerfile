FROM python:3.11-slim

WORKDIR /fastapi_auth

COPY ./requirements.txt /fastapi_auth/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /fastapi_auth

EXPOSE 8000

CMD ["uvicorn", "fastapi_auth.main:app", "--host", "0.0.0.0", "--port", "8000"]