# Speed Chime

Маленькая программа для **Forza Horizon**, которая издает звук (как в японских машинах), когда ты разгоняешься выше определенной скорости.

<details>
<summary><b>Инструкция на русском (нажми, чтобы открыть)</b></summary>

###Как запустить (готовую версию)

1. Скачай `SpeedChime.exe` со страницы **[Releases](https://github.com/JuniorThinks/SpeedChime/releases)**(скоро).
2. Запусти программу.
3. В самой игре зайди в **Настройки ➔ интерфейс и геймплей**, пролистай в самый низ и включи вывод данных:
   - **Data Out (Вывод данных):** Вкл
   - **IP-адрес:** `127.0.0.1`
   - **Порт:** `8888`
   - **Структура:** `Dash`
4. В окне программы поставь нужную скорость (по умолчанию 100 км/ч) и нажми **Start**.

###Настройки звука

- По умолчанию программа сама создает стандартный пищащий звук.
- Если хочешь поставить свой звук — нажми кнопку **Browse...** и выбери любой `.wav` файл.
- Нажми кнопку **Test**, чтобы послушать, как он звучит (играет 5 секунд).

</details>

<details>
<summary><b>English Guide (click to expand)</b></summary>

###How to Run (Pre-built EXE)

1. Download `SpeedChime.exe` from the **[Releases](https://github.com/JuniorThinks/SpeedChime/releases)**(soon) page.
2. Run the application.
3. In Forza Horizon, go to **Settings ➔ HUD & Gameplay**, scroll to the bottom, and enable telemetry:
   - **Data Out:** On
   - **Data Out IP Address:** `127.0.0.1`
   - **Data Out IP Port:** `8888`
   - **Data Out Structure:** `Dash`
4. Set your desired speed threshold in the app (100 km/h by default) and click **Start**.

###Sound Settings

- By default, the app generates a standard chime sound automatically.
- To use your custom sound, click **Browse...** and select any `.wav` file.
- Click **Test** to preview your sound (plays for 5 seconds).

</details>

---

<details>
<summary><b>For Developers / Запуск из кода</b></summary>

```bash
# Install dependencies / Установка зависимостей
pip install pygame

# Run script / Запуск
python main.py

# Build EXE / Сборка в EXE
pip install pyinstaller
pyinstaller --noconsole --onefile main.py
