FROM eclipse-temurin:21 AS build

WORKDIR /app

RUN curl -o installer.jar https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.1-47.3.0/forge-1.20.1-47.3.0-installer.jar && \
    mkdir server && \
    java -jar installer.jar --installServer server && \
    cd server && \
    echo "eula=true" > eula.txt

FROM ubuntu:25.04 AS run

WORKDIR /app

RUN apt-get update && \
    apt-get install -y screen openssh-server default-jdk

COPY --from=build /app/server .

RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "root:root" | chpasswd && \
    chmod +x run.sh

ENV SCREENDIR=/tmp/screen

EXPOSE 25565 22

CMD ["/usr/sbin/sshd", "-D"]
