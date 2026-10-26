# YouTube Recycle Bin

A tool for finding obscure YouTube videos with very low view counts. 
Filters videos below a set threshold (default is < 50 views, configurable).

## Features

- Search for videos with low view counts (upper limit filter).
- Strict keyword matching in the video title (case-insensitive).
- Support for year, month, and exact day date filters.
- Turbo mode for automatically paging through a large number of results.
- Sorting by relevance or duration.
- Thumbnail loading.

## Installation and Usage

The application is written in Python. Depending on your device (PC or Android), different GUI libraries and dependencies are used.

### Option 1: PC (Windows, macOS, Linux)
The PC version uses the standard `Tkinter` library, which is built into Python. `Pillow` is required for thumbnails.

1. Install Python 3.8 or higher (on Windows, make sure to check "Add Python to PATH").
2. Download `pc.py` and `requirements.txt` from this repository into the same folder.
3. Open a terminal in that folder and install dependencies:
   `pip install -r requirements.txt`
4. Run the application:
   `python pc.py` (or `python3 pc.py` on Linux/macOS).

### Option 2: Android (via Pydroid 3)
The Android version uses `Kivy`, as `Tkinter` does not work on mobile. You will need the **Pydroid 3** app (available on Google Play).

1. Install Pydroid 3 from the Play Store.
2. Open the app, go to the menu (three lines) and select **Pip**.
3. Go to the "Pip" tab, find and install the **kivy** library (it may take a few minutes).
4. Download `mobile.py` from this repository and save it to your phone.
5. Open Pydroid 3, tap the folder icon, find the downloaded file, and open it.
6. Tap the yellow "Play" button at the bottom of the screen to run. The first Kivy launch may take 10-20 seconds.

## How to use

1. In the "Query (in quotes)" field, enter your target word. The app will only show videos with this word in the title (case-insensitive).
2. In the "Extra word" field, you can specify context that will not be strictly checked in the title.
3. In the "Date" field, you can enter a year (2012), month (201209), or day (20120901). Ranges separated by a space are also supported (e.g., 2012 2014).
4. Select a sorting method.
5. Click the "Turbo Search" button. The program will start paging through the search results and display matching videos.
6. Videos with 0 views are automatically pinned to the top of the list.
7. Double-click a row to open the video in your browser.

## Configuration

All main parameters are at the top of the file (either `pc.py` or `mobile.py`). You can open the file in any text editor and change the following values:

### View threshold
By default, videos with fewer than 50 views are searched. To change this, find the line:
`MAX_VIEWS = 50`
and replace 50 with your desired value.

### Turbo search limit
Turbo mode automatically loads pages until it checks a certain number of videos. The default is 300. To change this, find the line:
`TURBO_LIMIT = 300`
and set your desired number.

### Request delay
To avoid being blocked by YouTube, there is a pause between requests in turbo mode. It is implemented in the code via `time.sleep(0.5)`. If you start getting 429 errors (too many requests), increase this value.

## Note
The script was written using AI (vibe-coding).

## License
MIT

---

# YouTube Recycle Bin (Русская версия)

Инструмент для поиска малоизвестных видео на YouTube. 
Ищет видео с просмотрами ниже заданного порога (по умолчанию < 50, порог можно менять).

## Возможности

- Поиск видео с малым количеством просмотров.
- Обязательный поиск по слову в названии (без учета регистра).
- Поддержка поиска по годам, месяцам и конкретным дням.
- Турбо-режим для автоматического пролистывания большого количества результатов.
- Сортировка по релевантности и по длительности.
- Загрузка превью видео.

## Установка и запуск

### Вариант 1: ПК (Windows, macOS, Linux)
Используется стандартная библиотека `Tkinter`. Для превьюшек нужен `Pillow`.

1. Установите Python 3.8+ (на Windows отметьте "Add Python to PATH").
2. Скачайте файлы `pc.py` и `requirements.txt` в одну папку.
3. Откройте терминал в этой папке и установите зависимости:
   `pip install -r requirements.txt`
4. Запустите: `python pc.py`

### Вариант 2: Android (Pydroid 3)
Используется библиотека `Kivy`. Понадобится приложение **Pydroid 3**.

1. Установите Pydroid 3.
2. Перейдите в меню -> **Pip**.
3. Найдите и установите библиотеку **kivy**.
4. Скачайте файл `mobile.py` и откройте его в Pydroid 3.
5. Нажмите кнопку "Play" для запуска.

## Настройка

### Порог просмотров
В начале файла найдите `MAX_VIEWS = 50` и измените 50 на нужное значение.

### Лимит турбо-поиска
Найдите строку `TURBO_LIMIT = 300` и укажите свое число.

### Задержка между запросами
Реализована через `time.sleep(0.5)`. Если получаете ошибки 429, увеличьте паузу.
