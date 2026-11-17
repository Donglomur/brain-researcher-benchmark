FROM --platform=linux/arm64 python@sha256:608e6ed31df49009fa6c242fb61b5386a1c002e40c2b9cb1958e0f1041aaf06a
ENV OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
COPY requirements.linux-arm64.lock WHEELS.json BASE_IMAGE.json /opt/science-lock/
COPY verify_artifacts.py verify_runtime.py /opt/science-lock/
COPY LICENSES/ /opt/science-lock/LICENSES/
COPY wheels/ /opt/science-wheels/
RUN --network=none python -I -B /opt/science-lock/verify_artifacts.py --root /opt/science-wheels --lock /opt/science-lock/WHEELS.json \
 && python -m pip install --no-index --find-links=/opt/science-wheels --only-binary=:all: --require-hashes --no-cache-dir --no-compile -r /opt/science-lock/requirements.linux-arm64.lock \
 && python -m pip check \
 && python -I -B /opt/science-lock/verify_runtime.py
WORKDIR /work
CMD ["python3"]
