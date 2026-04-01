<p align="center">
  <img src="data/Kadr.png" alt="Kadr" width="128">
</p>

<h1 align="center">Kadr</h1>

<p align="center">
  Поиск торрентов фильмов и сериалов через TMDB и Jackett
</p>

<p align="center">
  <img src="https://img.shields.io/badge/GTK-4-4a86cf?style=flat-square" alt="GTK 4">
  <img src="https://img.shields.io/badge/Libadwaita-1-3584e4?style=flat-square" alt="Libadwaita">
  <img src="https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square" alt="Python 3.10+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green?style=flat-square" alt="GPL-3.0"></a>
</p>


## О проекте

Kadr — приложение для поиска торрентов фильмов и сериалов.
Показывает каталог из TMDB с постерами и рейтингами, ищет торренты через публичные
Jackett-серверы и отправляет загрузку в любимый торрент-клиент — всё из одного окна.

## Возможности

- **Каталог** — популярные фильмы и сериалы из TMDB, постеры, рейтинги, бесконечная подгрузка
- **Поиск** — поиск по названию в реальном времени с пагинацией
- **Торренты** — поиск через публичные Jackett-серверы (jacred.xyz, jac-red.ru, jac.red), без настройки
- **Загрузка** — отправка в FDM, qBittorrent, Transmission, Deluge, KTorrent одним кликом
- **Автовыбор** — автоматический выбор работающего сервера, прокси и клиента
- **Настройки** — выбор сервера, TMDB-прокси, торрент-клиента с проверкой доступности
- **Локализация** — интерфейс на русском языке

## Установка

### Из исходников

```
git clone https://github.com/Cheviiot/Kadr.git
cd Kadr
./kadr
```

<details>
<summary><strong>Зависимости</strong></summary>

| Дистрибутив      | Команда                                                                         |
|------------------|---------------------------------------------------------------------------------|
| ALT Linux        | `apt-get install python3-module-pygobject3 libgtk4 libadwaita python3-module-requests` |
| Fedora           | `dnf install python3-gobject gtk4 libadwaita python3-requests`                  |
| Arch             | `pacman -S python-gobject gtk4 libadwaita python-requests`                      |
| Debian / Ubuntu  | `apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-requests`          |

</details>

## Использование

### Как работает Kadr

| Шаг | | |
|---|---|---|
| **1** | **Выбери фильм или сериал** | Найди в каталоге или через поиск (Ctrl+F) |
| **2** | **Открой детали** | Нажми на карточку — откроется страница с описанием |
| **3** | **Найди торрент** | Торренты загружаются автоматически с Jackett-серверов |
| **4** | **Скачай** | Нажми кнопку загрузки — файл откроется в торрент-клиенте |

### Горячие клавиши

| Действие    | Комбинация  |
|-------------|-------------|
| Поиск       | `Ctrl+F`    |
| Настройки   | `Ctrl+,`    |
| Выход       | `Ctrl+Q`    |

## Настройки

| Параметр         | Варианты                                  | По умолчанию   |
|------------------|-------------------------------------------|----------------|
| Торрент-сервер   | Автоматически / jacred.xyz / jac-red.ru / jac.red | Автоматически |
| TMDB-прокси      | Автоматически / Напрямую / APN Render     | Автоматически  |
| Торрент-клиент   | Автоматически / FDM / qBittorrent / Transmission / Deluge / KTorrent | Автоматически |

## Данные

| Путь                              | Содержимое           |
|-----------------------------------|----------------------|
| `~/.config/Kadr/settings.json`    | Настройки            |

## Участие в разработке

> Это личный проект. Kadr создаётся одним человеком для собственного использования при помощи ИИ.

Код полностью открыт. Если хотите помочь — Pull Request и Issue приветствуются:
исправление ошибок, новые функции, переводы.

## Лицензия

[GPL-3.0-or-later](LICENSE)
