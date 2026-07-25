"""
Speed Chime
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

# ====================== НАСТРОЙКИ ======================

UDP_IP = "127.0.0.1"
UDP_PORT = 8888
PACKET_SIZE = 324

VX_OFFSET = 32
VY_OFFSET = 36
VZ_OFFSET = 40

SPEED_MULTIPLIER = 3.6
SANITY_LIMIT = 500.0

DEFAULT_SOUND_FILE = "speed_chime.wav"
DEFAULT_THRESHOLD_KMH = 100


# ====================== ЗВУК ======================

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


# ====================== ПАРСЕР ======================

def parse_packet(data: bytes):
    if len(data) < PACKET_SIZE:
        return None
    try:
        vx = struct.unpack_from("<f", data, VX_OFFSET)[0]
        vy = struct.unpack_from("<f", data, VY_OFFSET)[0]
        vz = struct.unpack_from("<f", data, VZ_OFFSET)[0]
    except struct.error:
        return None

    if not all(-SANITY_LIMIT <= v <= SANITY_LIMIT for v in (vx, vy, vz)):
        return None

    raw_speed_ms = math.sqrt(vx * vx + vy * vy + vz * vz)
    speed_kmh = raw_speed_ms * SPEED_MULTIPLIER

    return speed_kmh


# ====================== GUI И ЛОГИКА ======================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Speed Chime")
        self.root.geometry("450x520+100+80")
        self.root.minsize(550, 520)
        self.root.configure(bg="#1a1a24")

        self.running = False
        self.worker = None
        self.sock = None
        self.pygame = None
        self.chime = None
        self.playing = False
        self.lock = threading.Lock()

        self.threshold = DEFAULT_THRESHOLD_KMH
        self.sound_path = None

        self.ui_speed = 0.0
        self.last_packet_t = 0.0

        self._build()

    def _build(self):
        pad = {"padx": 10, "pady": 6}

        frm = ttk.LabelFrame(self.root, text="Settings")
        frm.pack(fill="x", **pad)

        ttk.Label(frm, text="Speed threshold (km/h):").grid(
            row=0, column=0, sticky="w", **pad)
        self.thr_var = tk.StringVar(value=str(DEFAULT_THRESHOLD_KMH))
        ttk.Spinbox(frm, from_=1, to=500, increment=5,
                    textvariable=self.thr_var, width=10).grid(
            row=0, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Sound file (optional):").grid(
            row=1, column=0, sticky="w", **pad)
        self.snd_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.snd_var, width=30).grid(
            row=1, column=1, sticky="we", **pad)

        btns = ttk.Frame(frm)
        btns.grid(row=1, column=2, sticky="w", **pad)
        ttk.Button(btns, text="Browse...", command=self._browse).pack(side="left", padx=(0, 5))
        ttk.Button(btns, text="Test", command=self.test_sound).pack(side="left")

        live = ttk.LabelFrame(self.root, text="Live telemetry")
        live.pack(fill="x", **pad)
        self.l_speed = ttk.Label(live, text="Speed: 0.0 km/h",
                                 font=("Consolas", 20, "bold"))
        self.l_speed.pack(anchor="w", **pad)
        self.l_chime = ttk.Label(live, text="Chime: off", font=("Consolas", 12))
        self.l_chime.pack(anchor="w", **pad)

        logfrm = ttk.LabelFrame(self.root, text="Log")
        logfrm.pack(fill="both", expand=True, **pad)
        self.log = scrolledtext.ScrolledText(logfrm, height=10, state="disabled",
                                             font=("Consolas", 9))
        self.log.pack(fill="both", expand=True, **pad)

        ctl = ttk.Frame(self.root)
        ctl.pack(fill="x", **pad)
        self.start_btn = ttk.Button(ctl, text="Start", command=self.start)
        self.start_btn.pack(side="left", **pad)
        self.stop_btn = ttk.Button(ctl, text="Stop", command=self.stop,
                                   state="disabled")
        self.stop_btn.pack(side="left", **pad)
        ttk.Button(ctl, text="Quit", command=self._quit).pack(side="right", **pad)

        # Небольшая подпись о разработке в самом низу окна
        footer = ttk.Label(self.root, text="Developed with AI assistance (Gemini)",
                           font=("Segoe UI", 8), foreground="#888888")
        footer.pack(side="bottom", pady=(0, 4))

    def _browse(self):
        p = filedialog.askopenfilename(filetypes=[("WAV", "*.wav"), ("All", "*.*")])
        if p:
            self.snd_var.set(p)

    def test_sound(self):
        if self.running:
            self._log("Please click 'Stop' first to test the sound.")
            return

        self._read_settings()
        self._cleanup_audio()

        try:
            self._init_audio()
        except ImportError:
            self._log("Error: Module 'pygame' not found.")
            return
        except Exception as e:
            self._log(f"Audio init failed: {e}")
            return

        self._log("Testing sound (5 seconds)...")
        try:
            self.chime.play(loops=-1, maxtime=5000)
        except Exception as e:
            self._log(f"Test play error: {e}")

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _resolve_sound(self) -> str:
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        if self.sound_path and os.path.exists(self.sound_path):
            return self.sound_path
        c1 = os.path.join(base, DEFAULT_SOUND_FILE)
        if os.path.exists(c1):
            return c1
        c2 = os.path.join(os.getcwd(), DEFAULT_SOUND_FILE)
        if os.path.exists(c2):
            return c2
        out = os.path.join(base, DEFAULT_SOUND_FILE)
        self._log(f"Generating default chime -> {out}")
        try:
            generate_default_chime(out)
        except Exception as e:
            self._log(f"Chime generation failed: {e}")
        return out

    def _init_audio(self):
        import pygame
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=256)
        pygame.mixer.init()
        self.pygame = pygame
        self.chime = pygame.mixer.Sound(self._resolve_sound())
        self.chime.set_volume(0.7)

    def _read_settings(self):
        try:
            thr = float(self.thr_var.get())
        except ValueError:
            thr = DEFAULT_THRESHOLD_KMH
        snd = self.snd_var.get().strip() or None

        with self.lock:
            self.threshold = thr
            self.sound_path = snd

    def start(self):
        if self.running:
            return

        self._read_settings()

        try:
            self._init_audio()
        except ImportError:
            self._log("Error: Module 'pygame' not found. Run: pip install pygame")
            return
        except Exception as e:
            self._log(f"Audio init failed: {e}")
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((UDP_IP, UDP_PORT))
        except OSError as e:
            self._log(f"Bind failed: {e}")
            self.sock.close()
            return
        self.sock.settimeout(0.5)

        self.running = True
        self.playing = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._log(f"Listener started! Armed >= {self.threshold} km/h")

        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()
        self._refresh_ui()

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.worker:
            self.worker.join(timeout=1.0)
        self._cleanup_audio()
        self._log("Listener stopped.")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.l_chime.configure(text="Chime: -")

    def _quit(self):
        self.stop()
        self.root.destroy()

    def _cleanup_audio(self):
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
        if self.pygame:
            try:
                self.pygame.mixer.quit()
            except Exception:
                pass
            self.pygame = None
            self.chime = None

    def _run(self):
        try:
            while self.running:
                try:
                    data, _ = self.sock.recvfrom(4096)
                except socket.timeout:
                    continue

                speed_kmh = parse_packet(data)
                if speed_kmh is None:
                    continue

                self.ui_speed = speed_kmh
                self.last_packet_t = time.time()

                with self.lock:
                    thr = self.threshold

                is_fast = speed_kmh >= thr

                if is_fast and not self.playing:
                    try:
                        self.chime.play(loops=-1)
                        self.playing = True
                        self._log(f"CHIME ON  {speed_kmh:.1f} km/h")
                    except Exception as e:
                        self._log(f"Chime play error: {e}")
                elif (not is_fast) and self.playing:
                    try:
                        self.chime.stop()
                    except Exception:
                        pass
                    self.playing = False
                    self._log(f"CHIME OFF {speed_kmh:.1f} km/h")

        except Exception as e:
            self._log(f"Worker error: {e}")
        finally:
            self._cleanup_audio()

    def _refresh_ui(self):
        if not self.running:
            return

        self._read_settings()

        now = time.time()
        if self.last_packet_t == 0 or now - self.last_packet_t > 1.5:
            self.l_speed.configure(text="Speed: NO DATA", foreground="#ff7070")
        else:
            self.l_speed.configure(
                text=f"Speed: {self.ui_speed:.1f} km/h",
                foreground="#ffd84a")

        self.l_chime.configure(
            text=f"Chime: {'ON' if self.playing else 'off'}",
            foreground="#7fff7f" if self.playing else "#a0a0a0")

        self.root.after(100, self._refresh_ui)


# ====================== MAIN ======================

def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()