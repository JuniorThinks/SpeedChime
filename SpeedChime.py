# Файл: main.py
# -*- coding: utf-8 -*-

"""
Forza Horizon Universal Speed Chime
======================================
Created with AI assistance (Gemini) & juniorThinks
"""

import socket
import struct
import math
import time
import sys
import os
import wave
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

try:
    from lang import LANGUAGES
except ImportError:
    LANGUAGES = {"EN": {"title": "Error: lang.py not found"}, "RU": {"title": "Ошибка: lang.py не найден"}}
    print("Error: Could not import LANGUAGES from lang.py")

# ====================== НАСТРОЙКИ UDP ======================

UDP_IP = "127.0.0.1"
UDP_PORT = 8888
PACKET_SIZE = 324

# Смещение первой оси (Velocity X). Y и Z идут следом, поэтому читаем блоком
VX_OFFSET = 32

SPEED_MULTIPLIER = 3.6
SANITY_LIMIT = 500.0

DEFAULT_SOUND_FILE = "speed_chime.wav"
DEFAULT_THRESHOLD_KMH = 100


# ====================== УТИЛИТЫ ДЛЯ ПУТЕЙ ======================

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ====================== ГЕНЕРАТОР ЗВУКА ======================

def generate_default_chime(path: str) -> None:
    sample_rate = 22050
    duration = 0.6
    fade = int(sample_rate * 0.03)
    n = int(sample_rate * duration)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for i in range(n):
            t = i / sample_rate
            freq = 1000.0 if t < duration / 2 else 1500.0
            env = 1.0
            if i < fade:
                env = i / fade
            elif i > n - fade:
                env = (n - i) / fade
            sample = math.sin(2.0 * math.pi * freq * t) * env * 0.35
            sample = max(-1.0, min(1.0, sample))
            w.writeframes(struct.pack("<h", int(sample * 32767)))


# ====================== ПАРСЕР UDP ======================

def parse_packet(data: bytes):
    if len(data) < PACKET_SIZE:
        return None
    try:
        vx, vy, vz = struct.unpack_from("<3f", data, VX_OFFSET)
    except struct.error:
        return None

    if not (-SANITY_LIMIT <= vx <= SANITY_LIMIT and
            -SANITY_LIMIT <= vy <= SANITY_LIMIT and
            -SANITY_LIMIT <= vz <= SANITY_LIMIT):
        return None

    return math.hypot(vx, vy, vz) * SPEED_MULTIPLIER


# ====================== ГЛАВНОЕ ОКНО ======================

class App:
    def __init__(self, root):
        self.root = root
        self.root.geometry("450x550+100+80")
        self.root.minsize(575, 550)

        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.is_dark_mode = True
        self.running = False
        self.worker = None
        self.sock = None

        self.pygame = None
        self.chime = None
        self.playing = False

        self.threshold = DEFAULT_THRESHOLD_KMH
        self.sound_path = None
        self.ui_speed = 0.0
        self.last_packet_t = 0.0

        self.lang_var = tk.StringVar(value="RU")

        self._build_ui()
        self._apply_theme()
        self._apply_language()

    def _t(self, key):
        return LANGUAGES.get(self.lang_var.get(), LANGUAGES["EN"]).get(key, f"!{key}!")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        self.lf_settings = ttk.LabelFrame(self.root, text="")
        self.lf_settings.pack(fill="x", **pad)

        self.lbl_lang = ttk.Label(self.lf_settings, text="")
        self.lbl_lang.grid(row=0, column=0, sticky="w", **pad)
        lang_cb = ttk.Combobox(self.lf_settings, textvariable=self.lang_var,
                               values=list(LANGUAGES.keys()), state="readonly", width=5)
        lang_cb.grid(row=0, column=1, sticky="w", **pad)
        lang_cb.bind("<<ComboboxSelected>>", self._apply_language)

        self.lbl_thr = ttk.Label(self.lf_settings, text="")
        self.lbl_thr.grid(row=1, column=0, sticky="w", **pad)
        self.thr_var = tk.StringVar(value=str(DEFAULT_THRESHOLD_KMH))
        ttk.Spinbox(self.lf_settings, from_=1, to=500, increment=5,
                    textvariable=self.thr_var, width=10).grid(row=1, column=1, sticky="w", **pad)

        self.lbl_snd = ttk.Label(self.lf_settings, text="")
        self.lbl_snd.grid(row=2, column=0, sticky="w", **pad)
        self.snd_var = tk.StringVar()
        ttk.Entry(self.lf_settings, textvariable=self.snd_var, width=30).grid(row=2, column=1, sticky="we", **pad)

        btns_frame = ttk.Frame(self.lf_settings)
        btns_frame.grid(row=2, column=2, sticky="w", **pad)
        self.btn_browse = ttk.Button(btns_frame, text="", command=self._browse_sound)
        self.btn_browse.pack(side="left", padx=(0, 5))
        self.btn_test = ttk.Button(btns_frame, text="", command=self.test_sound)
        self.btn_test.pack(side="left")

        self.lf_live = ttk.LabelFrame(self.root, text="")
        self.lf_live.pack(fill="x", **pad)
        self.l_speed = ttk.Label(self.lf_live, text="Speed: 0.0 km/h", font=("Consolas", 22, "bold"))
        self.l_speed.pack(anchor="w", **pad)
        self.l_chime = ttk.Label(self.lf_live, text="Chime: off", font=("Consolas", 12))
        self.l_chime.pack(anchor="w", **pad)

        self.lf_log = ttk.LabelFrame(self.root, text="")
        self.lf_log.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(self.lf_log, height=10, state="disabled", font=("Consolas", 9),
                                             wrap="word")
        self.log.pack(fill="both", expand=True, padx=2, pady=2)

        ctl_frame = ttk.Frame(self.root)
        ctl_frame.pack(fill="x", **pad)

        self.start_btn = ttk.Button(ctl_frame, text="", command=self.start_listener)
        self.start_btn.pack(side="left", padx=(0, 5))
        self.stop_btn = ttk.Button(ctl_frame, text="", command=self.stop_listener, state="disabled")
        self.stop_btn.pack(side="left")

        self.btn_quit = ttk.Button(ctl_frame, text="", command=self._quit_app)
        self.btn_quit.pack(side="right")

        self.btn_theme = ttk.Button(ctl_frame, text="", command=self.toggle_theme)
        self.btn_theme.pack(side="right", padx=10)

        self.lbl_footer = ttk.Label(self.root, text="", font=("Segoe UI", 8))
        self.lbl_footer.pack(side="bottom", pady=(0, 4))

    # ====================== ЛОГИКА ТЕМЫ И ЯЗЫКА ======================

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self._apply_theme()
        self._update_theme_btn_text()

    def _apply_theme(self):
        style = ttk.Style()

        if self.is_dark_mode:
            bg_main, fg_main, bg_input, bg_btn, bg_btn_act = "#1a1a24", "#ffffff", "#2a2a35", "#3a3a45", "#4a4a55"
            self.root.configure(bg=bg_main)
            self.lbl_footer.configure(foreground="#888888")
        else:
            bg_main, fg_main, bg_input, bg_btn, bg_btn_act = "#f4f4f4", "#000000", "#ffffff", "#e0e0e0", "#d0d0d0"
            self.root.configure(bg=bg_main)
            self.lbl_footer.configure(foreground="#666666")

        style.configure(".", background=bg_main, foreground=fg_main)
        style.configure("TButton", background=bg_btn, foreground=fg_main, borderwidth=0, padding=4)
        style.map("TButton", background=[("active", bg_btn_act)])
        style.configure("TLabelframe", background=bg_main, foreground=fg_main)
        style.configure("TLabelframe.Label", background=bg_main, foreground=fg_main)

        style.configure("TEntry", fieldbackground=bg_input, foreground=fg_main, borderwidth=1)
        style.configure("TSpinbox", fieldbackground=bg_input, background=bg_btn, foreground=fg_main, borderwidth=1)

        style.configure("TCombobox", fieldbackground=bg_input, background=bg_btn, foreground=fg_main, borderwidth=1,
                        arrowcolor=fg_main)
        style.map("TCombobox",
                  fieldbackground=[("readonly", bg_input)],
                  selectbackground=[("readonly", bg_input)],
                  selectforeground=[("readonly", fg_main)],
                  foreground=[("readonly", fg_main)])

        self.root.option_add('*TCombobox*Listbox.background', bg_input)
        self.root.option_add('*TCombobox*Listbox.foreground', fg_main)
        self.root.option_add('*TCombobox*Listbox.selectBackground', bg_btn_act)
        self.root.option_add('*TCombobox*Listbox.selectForeground', fg_main)

        self.log.configure(bg=bg_input, fg=fg_main, insertbackground=fg_main)
        self._refresh_ui_elements()

    def _update_theme_btn_text(self):
        key = "theme_light" if self.is_dark_mode else "theme_dark"
        self.btn_theme.configure(text=self._t(key))

    def _apply_language(self, event=None):
        self.root.title(self._t("title"))
        self.lf_settings.config(text=self._t("settings"))
        self.lbl_lang.config(text=self._t("lang"))
        self.lbl_thr.config(text=self._t("threshold"))
        self.lbl_snd.config(text=self._t("sound_file"))
        self.btn_browse.config(text=self._t("browse"))
        self.btn_test.config(text=self._t("test"))
        self.lf_live.config(text=self._t("live"))
        self.lf_log.config(text=self._t("log_title"))
        self.start_btn.config(text=self._t("start"))
        self.stop_btn.config(text=self._t("stop"))
        self.btn_quit.config(text=self._t("quit"))
        self.lbl_footer.config(text=self._t("footer"))
        self._update_theme_btn_text()
        self._refresh_ui_elements()

    # ====================== ОСТАЛЬНАЯ ЛОГИКА ======================

    def _browse_sound(self):
        # === ДОБАВЛЕНЫ ФОРМАТЫ MP3 И OGG ===
        p = filedialog.askopenfilename(filetypes=[("Audio", "*.wav;*.mp3;*.ogg"), ("All files", "*.*")])
        if p:
            self.snd_var.set(p)
            # Если выбран MP3, сразу пишем предупреждение в лог
            if p.lower().endswith(".mp3"):
                self._log_to_console(self._t("warn_mp3"))

    def _log_to_console(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _resolve_sound_path(self) -> str:
        if self.sound_path and os.path.exists(self.sound_path):
            return self.sound_path

        c1 = get_resource_path(DEFAULT_SOUND_FILE)
        if os.path.exists(c1): return c1
        c2 = os.path.join(os.getcwd(), DEFAULT_SOUND_FILE)
        if os.path.exists(c2): return c2

        try:
            generate_default_chime(c1)
        except Exception:
            pass
        return c1

    def _init_audio_engine(self):
        if not self.pygame:
            import pygame
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
            pygame.mixer.init()
            self.pygame = pygame

        if self.chime:
            self.chime.stop()

        self.chime = self.pygame.mixer.Sound(self._resolve_sound_path())
        self.chime.set_volume(0.7)

    def _cleanup_audio_engine(self):
        try:
            if self.playing and self.chime:
                self.chime.stop()
        except Exception:
            pass
        self.playing = False

        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def test_sound(self):
        if self.running:
            self._log_to_console(self._t("test_first_stop"))
            return

        try:
            self.threshold = float(self.thr_var.get())
        except ValueError:
            self.threshold = DEFAULT_THRESHOLD_KMH
        self.sound_path = self.snd_var.get().strip() or None

        self._cleanup_audio_engine()
        try:
            self._init_audio_engine()
        except Exception as e:
            self._log_to_console(f"Audio error: {e}")
            return

        self._log_to_console(self._t("testing_sound"))
        try:
            self.chime.play(loops=-1, maxtime=5000)
        except Exception:
            pass

    def start_listener(self):
        if self.running: return

        try:
            self.threshold = float(self.thr_var.get())
        except ValueError:
            self.threshold = DEFAULT_THRESHOLD_KMH
        self.sound_path = self.snd_var.get().strip() or None

        # === ПРОВЕРЯЕМ ПРИ СТАРТЕ === (Если вписали путь вручную)
        if self.sound_path and self.sound_path.lower().endswith(".mp3"):
            self._log_to_console(self._t("warn_mp3"))

        try:
            self._init_audio_engine()
        except Exception as e:
            self._log_to_console(self._t("err_pygame") + f" ({e})")
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((UDP_IP, UDP_PORT))
        except OSError as e:
            self._log_to_console(f"Bind failed: {e}")
            self.sock.close()
            return
        self.sock.settimeout(0.5)

        self.running = True
        self.playing = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log_to_console(self._t("started").format(self.threshold))

        self.worker = threading.Thread(target=self._network_loop, daemon=True)
        self.worker.start()
        self._refresh_ui_elements()

    def stop_listener(self):
        if not self.running: return
        self.running = False
        if self.worker: self.worker.join(timeout=1.0)
        self._cleanup_audio_engine()
        self._log_to_console(self._t("stopped"))
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _quit_app(self):
        self.stop_listener()
        if self.pygame:
            try:
                self.pygame.mixer.quit()
            except Exception:
                pass
        self.root.destroy()

    def _network_loop(self):
        try:
            while self.running:
                try:
                    data, _ = self.sock.recvfrom(1024)
                except socket.timeout:
                    continue

                speed_kmh = parse_packet(data)
                if speed_kmh is None: continue

                self.ui_speed = speed_kmh
                self.last_packet_t = time.time()

                thr = self.threshold
                is_over = speed_kmh >= thr

                if is_over and not self.playing:
                    try:
                        self.chime.play(loops=-1)
                        self.playing = True
                    except Exception:
                        pass
                elif (not is_over) and self.playing:
                    try:
                        self.chime.stop()
                    except Exception:
                        pass
                    self.playing = False

        except Exception as e:
            self._log_to_console(f"Worker error: {e}")
        finally:
            self._cleanup_audio_engine()

    def _refresh_ui_elements(self):
        if not self.running and self.last_packet_t == 0:
            self.l_speed.configure(text=self._t("speed_no_data"), foreground="#ff7070")
            self.l_chime.configure(text="-", foreground="#a0a0a0")
            return

        now = time.time()
        if self.last_packet_t == 0 or now - self.last_packet_t > 1.5:
            self.l_speed.configure(text=self._t("speed_no_data"), foreground="#ff7070")
        else:
            prefix = self._t('live').split()[0] if self.lang_var.get() == "RU" else "Speed"
            accent_color = "#ffd84a" if self.is_dark_mode else "#0055aa"
            self.l_speed.configure(
                text=f"{prefix}: {self.ui_speed:.1f} км/ч" if self.lang_var.get() == "RU" else f"Speed: {self.ui_speed:.1f} km/h",
                foreground=accent_color)

        self.l_chime.configure(
            text=self._t("chime_on") if self.playing else self._t("chime_off"),
            foreground="#7fff7f" if self.playing else "#a0a0a0")

        if self.running:
            self.root.after(100, self._refresh_ui_elements)


# ====================== ТОЧКА ВХОДА ======================

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    main()