# A separately observed, immutable python:3.9.18-bullseye@sha256:<digest>
# Linux amd64 base must already be selected. No tag-only default is supplied.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
COPY feature_environment.py WHEEL_ARTIFACTS.json /opt/n055/
COPY wheelhouse/ /opt/n055/wheelhouse/
COPY wheel-lock.json requirements.lock /opt/n055/
RUN --network=none /usr/local/bin/python3.9 -I -B /opt/n055/feature_environment.py verify-wheels /opt/n055/wheelhouse /opt/n055/wheel-lock.json /opt/n055/requirements.lock
RUN --network=none /usr/local/bin/python3.9 -m pip install --no-index --no-cache-dir --no-compile --require-hashes --find-links=/opt/n055/wheelhouse -r /opt/n055/requirements.lock && /usr/local/bin/python3.9 -m pip check
WORKDIR /work
USER 65534:65534
