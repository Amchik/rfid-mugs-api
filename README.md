# `rfid-mugs-api`

Веб сервер и телеграм бот для RFID кружек.

## Развёртывание

1. Сбилдить docker image командой `docker build .` или скачать его [отсюда](https://github.com/ValgrindLLVM/rfid-mugs-api/pkgs/container/rfid-mugs-api).
2. Найти место для конфига и базы данных (т.е. директорию). Например, `/opt/rfid-mugs-api`. Скопировать туда файл
    `config.json` (из `config.example.json`).
3. Настроить сервер в `config.json`: поменять значения токенов и телеграм бота. Базу данных поставить `/storage/mugs.sqlite`.
4. Запустить докер контейнер этой прекрасной командой:
    ```console
    $ docker run \
        --restart on-failure:3 \
        --env CONFIG_PATH=/storage/config.json \
        -v /opt/rfid-mugs-api:/storage \
        -d \
        --name rfid-mugs-api-py-prod \
        -p 3030:8000 \
        ghcr.io/valgrindllvm/rfid-mugs-api:master
    ```
    Вместо `/opt/rfid-mugs-api` следует поставить вашу директорию на host машине.

## Принцип работы

Описан [вот тут](https://www.overleaf.com/read/rhbvhmzpfsmd#b9d6cd).
