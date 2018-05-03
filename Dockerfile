FROM fedora:28
LABEL \
    name="Greenwave application" \
    vendor="Greenwave developers" \
    license="GPLv2+" \
    build-date=""

# The caller should build a greenwave RPM package using ./rpmbuild.sh and then pass it in this arg.
ARG greenwave_rpm
# The caller can optionally provide a cacert url
ARG cacert_url=undefined

COPY $greenwave_rpm /tmp
RUN dnf -y install \
    python2-gunicorn \
    python-memcached \
    /tmp/$(basename $greenwave_rpm) \
    && dnf -y clean all \
    && rm -rf /tmp/*

RUN if [ "$cacert_url" != "undefined" ]; then \
        cd /etc/pki/ca-trust/source/anchors \
        && curl -O --insecure $cacert_url \
        && update-ca-trust extract; \
    fi
USER 1001
EXPOSE 8080
ENTRYPOINT gunicorn --workers 8 --bind 0.0.0.0:8080 --access-logfile=- --enable-stdio-inheritance greenwave.wsgi:app
