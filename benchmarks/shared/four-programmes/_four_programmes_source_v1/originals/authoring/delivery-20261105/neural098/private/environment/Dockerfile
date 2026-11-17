# Unbuilt dependency recipe. Tag/digest and transitive closure remain blockers.
FROM python:3.12.8-slim
COPY private/environment/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /task
COPY public /task/public
COPY private /task/private
ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
# No model, reference, verifier or dataset command runs during the image build.
