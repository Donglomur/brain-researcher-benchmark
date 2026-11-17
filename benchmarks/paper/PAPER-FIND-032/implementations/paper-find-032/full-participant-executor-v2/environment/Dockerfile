# Source recipe only: no image build, import check or scientific run has occurred.
# Deliberately one architecture, matching the selected FIND032 native scope.
FROM --platform=linux/amd64 python@sha256:a8e0a3090316aed0b11037aac613aef32fb1747dcc1dcb5c0f6c727a0113a07f AS numerical-environment
SHELL ["/bin/sh", "-ec"]
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    RPY2_CFFI_MODE=API \
    R_HOME=/usr/lib/R \
    LD_LIBRARY_PATH=/usr/lib/R/lib \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MPLBACKEND=Agg \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1
WORKDIR /opt/find032-environment
COPY environment.lock.json verify_apt_snapshot.py verify_environment.py ./
COPY requirements-bootstrap.txt requirements-wheels.txt requirements-rpy2.txt ./
COPY sources.list /etc/apt/sources.list
# Remove only the selected base's standard live repository configuration.
# Keep signature verification; only historical Valid-Until expiration is disabled.
RUN rm -f /etc/apt/sources.list.d/debian.sources \
 && python -I -S -B verify_apt_snapshot.py --lock environment.lock.json --mode remote > apt-remote.json \
 && apt-get update \
 && python -I -S -B verify_apt_snapshot.py --lock environment.lock.json --mode apt-cache > apt-cache.json \
 && apt-get install -y --no-install-recommends \
      ca-certificates tzdata git build-essential libffi-dev libgomp1 \
      r-base-core=4.2.2.20221110-2 r-base-dev=4.2.2.20221110-2 \
      r-cran-coda r-cran-matrix r-cran-pbapply r-cran-mvtnorm \
      r-cran-stringr r-cran-matrixmodels r-cran-rcpp r-cran-rcppeigen r-cran-hypergeo \
 && dpkg-query -W -f='${binary:Package}\t${Version}\n' > dpkg-installed.txt
RUN python -m pip install --require-hashes --no-deps --only-binary=:all: -r requirements-bootstrap.txt \
 && python -m pip install --require-hashes --no-deps --only-binary=:all: -r requirements-wheels.txt \
 && python -m pip install --require-hashes --no-deps --no-build-isolation -r requirements-rpy2.txt
# CRAN's public Git mirror is the selected source identity. No floating tag,
# install.packages(), remotes resolver, or archive checksum is substituted.
RUN mkdir -p /opt/find032-upstream/BayesFactor \
 && git -C /opt/find032-upstream/BayesFactor init \
 && git -C /opt/find032-upstream/BayesFactor remote add origin https://github.com/cran/BayesFactor.git \
 && git -c credential.helper= -C /opt/find032-upstream/BayesFactor fetch --depth=1 origin fd79157d60179efc68b36ea7b88ae7833ccedfd3 \
 && test "$(git -C /opt/find032-upstream/BayesFactor rev-parse FETCH_HEAD)" = fd79157d60179efc68b36ea7b88ae7833ccedfd3 \
 && git -C /opt/find032-upstream/BayesFactor checkout --detach fd79157d60179efc68b36ea7b88ae7833ccedfd3 \
 && R CMD INSTALL /opt/find032-upstream/BayesFactor
RUN python -m pip check \
 && python -I -B verify_environment.py --lock environment.lock.json > environment-imports.json
# Both candidate arms use this same final image. Trusted evaluator code and
# protected reference/data are absent; the host mounts each explicitly later.
FROM numerical-environment AS candidate
CMD ["python"]
# This supplies reference dependencies; a separate reference-production command
# and selected native owner are still required. No reference is produced here.
FROM numerical-environment AS reference-environment
CMD ["python"]
