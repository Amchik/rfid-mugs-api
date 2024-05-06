FROM python:3.12 AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./requirements.txt .
RUN pip3 install --no-cache-dir --upgrade -r /app/requirements.txt

FROM python:3.12-slim

WORKDIR /app

COPY . .
COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

CMD ["python3", "main.py"]