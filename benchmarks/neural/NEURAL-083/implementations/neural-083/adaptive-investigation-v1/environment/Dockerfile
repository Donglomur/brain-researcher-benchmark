# Source recipe only. No build, pull, installation or numerical import was run.
FROM --platform=linux/amd64 python@sha256:a8e0a3090316aed0b11037aac613aef32fb1747dcc1dcb5c0f6c727a0113a07f
SHELL ["/bin/sh", "-ec"]
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 LANG=C.UTF-8 LC_ALL=C.UTF-8 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WORKDIR /opt/neural083-environment
COPY environment.lock.json requirements-bootstrap.txt requirements-runtime.txt verify_apt_snapshot.py verify_environment.py ./
COPY sources.list /etc/apt/sources.list
RUN rm -f /etc/apt/sources.list.d/debian.sources \
 && python -I -S -B verify_apt_snapshot.py --lock environment.lock.json --mode remote > apt-remote.json \
 && apt-get update \
 && python -I -S -B verify_apt_snapshot.py --lock environment.lock.json --mode apt-cache > apt-cache.json \
 && apt-get install -y --no-install-recommends libgomp1 libstdc++6 \
 && dpkg-query -W -f='${binary:Package}\t${Version}\n' > dpkg-installed.txt
RUN python -I -B -m pip --isolated install --require-hashes --no-deps --only-binary=:all: -r requirements-bootstrap.txt \
 && python -I -B -m pip --isolated install --require-hashes --no-deps --only-binary=:all: -r requirements-runtime.txt \
 && python -I -B -m pip --isolated check \
 && python -I -B verify_environment.py --lock environment.lock.json > environment-imports.json
# The actual trusted native transport overrides this command and entrypoint.
# No task code, data, answers, credentials, model server or weights are included.
CMD ["python"]
