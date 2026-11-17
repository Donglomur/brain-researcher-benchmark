# A separately selected immutable base reference is required; no mutable default.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
COPY requirements.lock /build/requirements.lock
COPY wheelhouse /build/wheelhouse
COPY feature_environment.py /opt/neural055/feature_environment.py
COPY verify_wheels.py /opt/neural055/verify_wheels.py
COPY ENVIRONMENT_LOCK.json /opt/neural055/ENVIRONMENT_LOCK.json
RUN python -I -B /opt/neural055/verify_wheels.py \
      --helper /opt/neural055/feature_environment.py \
      --lock /opt/neural055/ENVIRONMENT_LOCK.json --wheelhouse /build/wheelhouse \
    && python -I -B -m pip install --no-index --no-deps --require-hashes \
      --only-binary=:all: --find-links=/build/wheelhouse -r /build/requirements.lock \
    && python -I -B -m pip check
COPY inspect_environment.py /opt/neural055/inspect_environment.py
# Future provisioning inspection loads packages, never a model/checkpoint or dataset.
RUN python -I -B /opt/neural055/inspect_environment.py --lock /opt/neural055/ENVIRONMENT_LOCK.json --capabilities
WORKDIR /tmp
CMD ["python"]
