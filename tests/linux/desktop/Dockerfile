# A complete Linux desktop (XFCE) reachable from a browser (noVNC), to see the application as a user would.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive LANG=hu_HU.UTF-8 LC_ALL=hu_HU.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
        xfce4 xfce4-notifyd dbus-x11 xterm \
        tigervnc-standalone-server tigervnc-common novnc websockify \
        python3 fonts-noto-core fonts-noto-color-emoji fonts-dejavu-core adwaita-icon-theme locales \
        libnotify-bin gnome-keyring libx11-6 libxft2 libfontconfig1 ca-certificates \
    && locale-gen hu_HU.UTF-8 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash demo
COPY start.sh fake_api.py /opt/desktop/
RUN chmod +x /opt/desktop/start.sh
EXPOSE 6080
CMD ["/opt/desktop/start.sh"]
