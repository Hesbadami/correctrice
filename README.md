![Architecture](correctrice.jpg)


Telegram Bot API docker-compose:

```yaml
services:
    telegram-bot-api:
        image: 'aiogram/telegram-bot-api:latest'
        extra_hosts:
            - 'host.docker.internal:host-gateway'
        environment:
            - TELEGRAM_LOCAL=1
            - TELEGRAM_API_HASH=hash
            - TELEGRAM_API_ID=id
        volumes:
            - './volume:/var/lib/telegram-bot-api'
        restart: always
        container_name: telegram-bot-api
        ports:
            - '8081:8081'
```


NATS docker-compose:

```yaml
services:
  nats:
    image: nats:latest
    container_name: nats
    restart: always
    ports:
      - "127.0.0.1:4222:4222"
      - "127.0.0.1:8222:8222"
      - "127.0.0.1:6222:6222"
    command:
      - "--jetstream"
      - "--http_port=8222"  # Enable monitoring
    volumes:
      - nats_data:/data

  nats-box:
    image: natsio/nats-box:latest
    container_name: kopilot-nats-box
    depends_on:
      - nats
    command: sleep infinity  # Keep container running for debugging
    restart: unless-stopped

volumes:
  nats_data:
    external: true
```

MySQL docker-compose:

```yaml
services:
  mysql:
    image: mysql:latest
    container_name: mysql
    restart: always
    ports:
      - "127.0.0.1:3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql
    environment:
      - MYSQL_ROOT_PASSWORD=password

  phpmyadmin:
    image: phpmyadmin/phpmyadmin:latest
    container_name: phpmyadmin
    restart: always
    ports:
      - "8080:80"
    environment:
      - PMA_HOST=mysql
      - MYSQL_ROOT_PASSWORD=password
    depends_on:
      - mysql

volumes:
  mysql-data:
    external: true
```