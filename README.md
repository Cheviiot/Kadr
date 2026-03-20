<h1 align="center">Kadr</h1>

<p align="center">
  <strong>🎬 Элегантное приложение для поиска торрентов фильмов и сериалов</strong>
</p>

<p align="center">
  <a href="https://github.com/Cheviiot/Kadr/releases"><img src="https://img.shields.io/github/v/release/Cheviiot/Kadr?style=flat-square&color=blue" alt="Release"></a>
  <a href="https://github.com/Cheviiot/Kadr/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Cheviiot/Kadr?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <a href="#-установка">Установка</a> •
  <a href="#-особенности">Особенности</a> •
  <a href="#-запуск">Запуск</a> •
  <a href="#-лицензия">Лицензия</a>
</p>

---

## ✨ Особенности

- 🔍 **Поиск фильмов и сериалов** — интеграция с TMDB
- 🧲 **Поиск торрентов** — через публичные Jackett серверы (без настройки!)
- ⬇️ **Загрузка в один клик** — отправка в FDM, qBittorrent, Transmission, Deluge, KTorrent
- 🎨 **Нативный интерфейс** — GTK4 + libadwaita
- 🚀 **Быстрая работа** — Python, асинхронная загрузка изображений

---

## 🛠️ Технологии

| Компонент | Стек |
|-----------|------|
| UI | GTK4 + libadwaita |
| Язык | Python 3.10+ |
| HTTP | requests |
| API | TMDB, Jackett |

---

## 📦 Установка зависимостей

### Fedora

```bash
sudo dnf install gtk4-devel libadwaita-devel python3-gobject python3-requests
```

### Ubuntu / Debian

```bash
sudo apt install libgtk-4-dev libadwaita-1-dev gir1.2-adw-1 python3-gi python3-requests
```

### Arch Linux

```bash
sudo pacman -S gtk4 libadwaita python-gobject python-requests
```

Или через pip (PyGObject требует системных библиотек GTK):

```bash
pip install requests PyGObject
```

---

## 🚀 Запуск

### Из исходников

```bash
git clone https://github.com/Cheviiot/Kadr.git
cd Kadr
./kadr
```

**Горячие клавиши:**
- `Ctrl+F` — Поиск
- `Ctrl+Q` — Выход

---

## 📁 Структура проекта

```
kadr                             # Исполняемый лаунчер
pyproject.toml                   # Сборка (hatchling)
data/
  Kadr.png                       # Иконка приложения
  io.github.cheviiot.kadr.desktop
src/kadr/
  __init__.py                    # Версия, пути, константы
  __main__.py                    # Entry point, проверка gi
  application.py                 # Adw.Application
  window.py                      # Главное окно
  utils.py                       # Утилиты (async, кеш изображений)
  data/
    style.css                    # Кастомные стили
  services/
    settings.py                  # Настройки (~/.config/Kadr/)
    tmdb.py                      # TMDB API
    jackett.py                   # Jackett торрент-поиск
    downloads.py                 # Менеджер загрузок
  views/
    home.py                      # Главный вид (сетка, поиск, табы)
    detail.py                    # Детали фильма/сериала + торренты
    settings_dialog.py           # Диалог настроек
  widgets/
    media_card.py                # Карточка фильма/сериала
    torrent_row.py               # Строка торрента
archive/                         # Предыдущая версия (Go + Wails v3)
```

---

## 📄 Лицензия

[MIT](LICENSE)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/Cheviiot">Cheviiot</a>
</p>
