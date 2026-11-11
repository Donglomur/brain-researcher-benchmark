FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /task
# Artifact stdlib tools only; image is unbuilt and base digest remains unbound.
# Author training needs a separately resolved .[c4] lock, data and permitted VAE inputs.
