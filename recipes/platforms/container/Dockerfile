# recipes/platforms/container/Dockerfile — Heimdall and its stack in one image (Ubuntu 24.04, as the lab PC).
#
# From the Heimdall folder (the context; Dockerfile.dockerignore keeps its ignored trees out):
#   docker build -f recipes/platforms/container/Dockerfile -t heimdall .
#   docker build -f recipes/platforms/container/Dockerfile --build-arg PACKAGES=core --build-arg ROOT_CORES=2 -t heimdall:core .
#
# A work dir is mounted, never copied in, at the same path inside as outside:
#   docker run --rm -it --user "$(id -u):$(id -g)" -v "$HOME/Github/Top-Quark:$HOME/Github/Top-Quark" -w "$HOME/Github/Top-Quark" heimdall
#
# The build takes hours (ROOT alone is 1–2 h) and ~25 GB of disk while it runs; give Docker 3 GB of
# memory per ROOT core (root_cores). The machine root is /opt/himinbjorg (HEP_MACHINE); its forge/
# (downloads, sources, builds, pixi and its package cache) is removed in the same layer, so the image
# keeps the installs only (docs/framework/targets/container.md). The stack is built on a conda base
# (docs/conda/): apt gives only the Python that runs the builder, the certificates it downloads with,
# and bzip2 and xz for its archive checks (tar -t).
# --build-arg PACKAGES=@core-conda: the core ready-made from conda-forge, in minutes.

FROM ubuntu:24.04

ARG PACKAGES=@primary
ARG CORES=0
ARG ROOT_CORES=0
ARG GRAPHICS=OFF
ARG GEANT4_DATA=ON

ENV LANG=C.UTF-8 HEP_MACHINE=/opt/himinbjorg

COPY . /opt/heimdall

RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates bzip2 xz-utils && \
    python3 /opt/heimdall/recipes/build_stack.py packages="$PACKAGES" \
        cores="$CORES" root_cores="$ROOT_CORES" graphics="$GRAPHICS" geant4_data="$GEANT4_DATA" && \
    bash -c 'source /opt/heimdall/setup.sh && make -C "$HEP" all' && \
    rm -rf /opt/himinbjorg/forge /var/lib/apt/lists/* /root/.cache/pip && \
    chmod -R a+rX /opt/heimdall /opt/himinbjorg

RUN echo '[ -n "$BASH_VERSION" ] && HEP_MACHINE=/opt/himinbjorg . /opt/heimdall/setup.sh' > /etc/profile.d/hep.sh && \
    echo 'source /etc/profile.d/hep.sh' >> /etc/bash.bashrc

CMD ["bash"]
