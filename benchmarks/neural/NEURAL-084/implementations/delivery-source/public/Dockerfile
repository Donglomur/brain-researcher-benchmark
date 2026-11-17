FROM python:3.11.9-slim-bookworm
WORKDIR /task
COPY requirements.txt /task/requirements.txt
RUN python -m pip install --no-cache-dir -r /task/requirements.txt
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
# Build recipe only. No image has been built or scientifically qualified.
