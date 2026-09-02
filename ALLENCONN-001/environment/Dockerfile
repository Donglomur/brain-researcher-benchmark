FROM python:3.10

# allensdk pins an old numpy that does not build on 3.12; Python 3.10 is required.
# Versions pinned to a combination verified to install and run end-to-end
# (allensdk 2.16.2 with numpy 1.23.5 / pandas 1.5.3 / scipy 1.10.1 / h5py 3.16.0).
RUN pip install --no-cache-dir \
      numpy==1.23.5 \
      pandas==1.5.3 \
      scipy==1.10.1 \
      h5py==3.16.0 \
      allensdk==2.16.2

WORKDIR /app
