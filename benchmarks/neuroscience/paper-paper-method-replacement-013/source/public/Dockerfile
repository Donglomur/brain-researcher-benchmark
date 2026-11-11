FROM python:3.12.8-slim
WORKDIR /task
COPY public/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
# Source recipe only. Base digest/network dependency build is unqualified.
