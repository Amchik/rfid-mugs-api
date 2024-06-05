# `rfid-mugs-api`

Веб сервер и телеграм бот для RFID кружек.

> Временное предназначение проекта заключается в хранении [моих](https://github.com/Amchik)
> кружек и прочих вещей с одной стороны на самом видном месте, а с другой под замком.

## Ту-ду лист

- [ ] Рефактор кода (везде, где проставлены `# NOTE:` или `# TODO:`)
- [ ] Больше безопасности (апи токены, рейтлимиты и прочее)
- [ ] Журнал плохих людей (кто взял кружку и не пикнул её)

## Развёртывание

1. Сбилдить docker image командой `docker build .` или скачать его [отсюда](https://github.com/Amchik/rfid-mugs-api/pkgs/container/rfid-mugs-api).
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
        ghcr.io/amchik/rfid-mugs-api:master
    ```
    Вместо `/opt/rfid-mugs-api` следует поставить вашу директорию на host машине.
5. Настроить nginx или любой другой свой веб сервер на reverse proxy (из команды выше, порт будет 3030).

## Принцип работы

Описан [вот тут](https://www.overleaf.com/read/rhbvhmzpfsmd#b9d6cd).
