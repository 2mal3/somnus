FROM eclipse-temurin:21-jdk AS build

WORKDIR /app

RUN curl -o server.jar https://api.papermc.io/v2/projects/paper/versions/1.21.3/builds/81/downloads/paper-1.21.3-81.jar && \
    echo "eula=true" > eula.txt && \
    java -Xms1G -Xmx1G -Dpaperclip.patchonly=true -jar server.jar --nogui


FROM eclipse-temurin:21-jdk AS run

WORKDIR /app

COPY --from=build /app .

RUN apt-get update && \
    apt-get install -y screen openssh-server

RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config && \
    echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config && \
    echo "root:root" | chpasswd && \
    echo "java -Xms1G -Xmx1G -jar server.jar --nogui" > start.sh && \
    chmod +x start.sh && \
    mkdir /var/run/sshd

EXPOSE 25565 22

CMD ["/usr/sbin/sshd", "-D"]
