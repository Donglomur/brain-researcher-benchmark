ARG THALAMUS_RUNTIME=neurobench-thalamus-runtime:delivery-20261105
FROM ${THALAMUS_RUNTIME}
USER 0:0
COPY --chown=65534:65534 private/grader.py private/asset_io.py private/reference_pin.json private/fixed_reference.json /package/private/
COPY --chown=65534:65534 private/core/ /package/private/core/
COPY --chown=65534:65534 public/SESSION_MANIFEST.json /package/public/SESSION_MANIFEST.json
USER 65534:65534
WORKDIR /package
ENTRYPOINT ["python", "-I", "/package/private/grader.py"]
