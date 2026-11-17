FROM --platform=linux/arm64 python:3.12.8-slim-bookworm@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0
COPY public/environment/debian-runtime.lock /tmp/debian-runtime.lock
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends $(cat /tmp/debian-runtime.lock) && rm -rf /var/lib/apt/lists/*
COPY public/environment/python-requirements.lock /tmp/python-requirements.lock
RUN python -m pip install --no-cache-dir --only-binary=:all: --no-deps --require-hashes -r /tmp/python-requirements.lock && python -m pip check
COPY public/environment/R-4.3.1-prefix.tar.gz /tmp/R-4.3.1-prefix.tar.gz
COPY public/environment/extract_runtime.py /tmp/extract_runtime.py
RUN python -I /tmp/extract_runtime.py /tmp/R-4.3.1-prefix.tar.gz && rm /tmp/R-4.3.1-prefix.tar.gz
COPY public/environment/check_runtime.py /tmp/check_runtime.py
COPY public/environment/python_expected_versions.json /tmp/python_expected_versions.json
RUN python -I /tmp/check_runtime.py
ENV PATH="/opt/thalamus/R-4.3.1/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
USER 65534:65534
WORKDIR /output
ENTRYPOINT ["python", "-I", "/program/program.py", "--input", "/input", "--out", "/output"]
