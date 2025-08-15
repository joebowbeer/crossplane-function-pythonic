FROM python:3.13-slim-trixie AS image

WORKDIR /root/pythonic
COPY pyproject.toml /root/pythonic
COPY crossplane /root/pythonic/crossplane
WORKDIR /
RUN \
  set -eux && \
  cd /root/pythonic && \
  pip install --root-user-action ignore --no-build-isolation setuptools==80.9.0 && \
  pip install --root-user-action ignore --no-build-isolation . && \
  pip uninstall --root-user-action ignore --yes setuptools && \
  cd .. && \
  rm -rf .cache pythonic && \
  groupadd --gid 2000 pythonic && \
  useradd --uid 2000 --gid pythonic --home-dir /opt/pythonic --create-home --shell /usr/sbin/nologin pythonic

USER pythonic:pythonic
WORKDIR /opt/pythonic
EXPOSE 9443
ENTRYPOINT ["python", "-m", "crossplane.pythonic.main"]
