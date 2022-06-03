# syntax=docker/dockerfile:1

# =========BASE BUILDER IMAGE=======
# Builder image
FROM ubuntu:18.04 AS base

# apt packages
ENV DEBIAN_FRONTEND noninteractive
RUN --mount=type=cache,target=/var/cache/apt apt-get -qq update \
    && apt-get -yqq upgrade \
    && apt-get install -yqq --no-install-recommends \
        sudo curl ssh git nmap wget man locate iputils-ping telnet unzip nano moreutils gettext apt-transport-https libssl-dev libxslt1.1 fonts-liberation liblcms2-2 libpq5 libldap-2.4-2 libsasl2-2 locales-all zlibc bzip2 ca-certificates gettext-base xz-utils libtinfo-dev libncurses5-dev ncurses-doc make zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev llvm libncursesw5-dev tk-dev libxmlsec1-dev libffi-dev liblzma-dev adduser lsb-base build-essential libxml2-dev libxslt1-dev libpq-dev libldap2-dev libsasl2-dev libopenjp2-7-dev libjpeg-turbo8-dev libtiff5-dev libfreetype6-dev liblcms2-dev libwebp-dev

#python3-babel python3-chardet python3-dateutil python3-decorator python3-docutils python3-feedparser python3-html2text python3-pil python3-jinja2 python3-libsass python3-lxml python3-mako python3-mock python3-passlib python3-polib python3-psutil python3-psycopg2 python3-pydot python3-pyparsing python3-pypdf2 python3-qrcode python3-reportlab python3-requests python3-suds python3-tz python3-vatnumber python3-vobject python3-werkzeug python3-xlsxwriter python3-pyldap python3-dev python3-venv python3-pip python3-libxml2

# Ubuntu user
RUN useradd -rm -d /home/ubuntu -s /bin/bash -u 1001 ubuntu

# Initial waft build
ENV GIT_AUTHOR_NAME "Renzo Brown"
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV LC_ALL en_US.UTF-8
USER ubuntu
WORKDIR /home/ubuntu
#ARG PROJECT_URL
#RUN --mount=type=ssh git clone ${PROJECT_URL} odoo
RUN mkdir -p odoo
COPY --chown=ubuntu auto/baseimage/ /home/ubuntu/odoo/
#bootstrap build common custom/src/addons.yaml custom/src/repos.yaml .env-shared .python-version requirements.txt run shell auto/baseimage waftlib


#bootstrap build common custom/src/addons.yaml custom/src/repos.yaml .env-shared .python-version requirements.txt run shell auto/baseimage
WORKDIR /home/ubuntu/odoo
RUN ls -al .
RUN chmod +x bootstrap \
    && ./bootstrap
RUN --mount=type=cache,target=/home/ubuntu/.cache/pip --mount=type=ssh chmod +x build \
    && ./build

# =========REBUILD IMAGE=======
# Rebuild - this is the last step and much faster
FROM base AS rebuild
EXPOSE 8069 8072
ENV GIT_AUTHOR_NAME "Renzo Brown"
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV LC_ALL en_US.UTF-8
USER ubuntu
WORKDIR /home/ubuntu/odoo
COPY --chown=ubuntu . odoo/
RUN --mount=type=cache,target=/home/ubuntu/.cache/pip --mount=type=ssh ./build

# =========RUNTIME IMAGE=======
# Image used to run a waft build
FROM ubuntu:18.04 AS runtime
ENV DEBIAN_FRONTEND noninteractive

RUN --mount=type=cache,target=/var/cache/apt apt-get -qq update \
    && apt-get -yqq upgrade \
    && apt-get install -yqq --no-install-recommends \
        sudo ruby ruby-dev curl apt-transport-https libffi-dev build-essential

# wkhtmltopdf
ARG WKHTMLTOPDF_VERSION=0.12.5
ARG WKHTMLTOPDF_CHECKSUM='db48fa1a043309c4bfe8c8e0e38dc06c183f821599dd88d4e3cea47c5a5d4cd3'
RUN --mount=type=cache,target=/var/cache/apt curl -SLo wkhtmltox.deb https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/${WKHTMLTOPDF_VERSION}/wkhtmltox_${WKHTMLTOPDF_VERSION}-1.bionic_amd64.deb \
    && echo "${WKHTMLTOPDF_CHECKSUM}  wkhtmltox.deb" | sha256sum -c \
    && apt-get install -yqq --no-install-recommends ./wkhtmltox.deb \
    && rm wkhtmltox.deb \
    && echo "wkhtmltopdf: " && wkhtmltopdf --version && which wkhtmltopdf

# node
ARG NODE_VERSION=6
RUN --mount=type=cache,target=/var/cache/apt curl -sL https://deb.nodesource.com/setup_$NODE_VERSION.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs=$NODE_VERSION.\* \
    && echo "Node: " && node -v && which node \
    && echo "NPM: " && npm -v && which npm \
    && rm -Rf /var/lib/apt/lists/* /tmp/* \
    && ln -s /usr/bin/nodejs /usr/local/bin/node

# node plugins
run npm install -g less@2 less-plugin-clean-css@1 \
    && rm -rf ~/.npm /tmp/*

# special case to get bootstrap-sass, required by odoo for sass assets
run gem install --no-rdoc --no-ri --no-update-sources autoprefixer-rails --version '<9.8.6' \
    && gem install --no-rdoc --no-ri --no-update-sources bootstrap-sass --version '<3.4' \
    && rm -rf ~/.gem /var/lib/gems/*/cache/

run apt-get update && apt-get install -yqq --no-install-recommends libpq-dev

RUN useradd -rm -d /home/ubuntu -s /bin/bash -u 1001 ubuntu
COPY --from=0 /home/ubuntu/odoo /home/ubuntu/odoo
WORKDIR /home/ubuntu/odoo
CMD ["./run"]
