# AllenSDK requires Python 3.10.
FROM python:3.10

# Pinned to the versions verified for this task. Two pins are load-bearing for AllenSDK 2.16.2:
#   * setuptools<81 keeps pkg_resources importable (AllenSDK imports it at module load);
#   * statsmodels==0.13.5 keeps statsmodels.sandbox.stats.multicomp.multipletests importable
#     (removed in statsmodels 0.14+), which AllenSDK's receptive-field code imports on load.
# scikit-learn provides the linear decoder.
RUN pip install --no-cache-dir \
      "setuptools<81" \
      allensdk==2.16.2 \
      numpy==1.23.5 \
      pandas==1.5.3 \
      scipy==1.10.1 \
      scikit-learn==1.3.2 \
      h5py==3.16.0 \
      statsmodels==0.13.5 \
      pynwb==2.8.3 \
      hdmf==6.2.0 \
      tables==3.10.1
WORKDIR /app
