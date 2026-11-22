"""Звуки: игра сама синтезирует их при первом запуске (файлы не нужны).

Если со звуком что-то пойдёт не так, игра просто продолжит работать без него.
"""
import math
import os
import random
import struct
import threading
import time
import wave

RATE = 22050
VERSION = 'v1'


def _tone(f0, f1, dur, vol=0.4, square=False, decay=4.0):
    n = max(1, int(RATE * dur))
    attack = RATE * 0.004
    out = []
    phase = 0.0
    for i in range(n):
        t = i / n
        phase += 2 * math.pi * (f0 + (f1 - f0) * t) / RATE
        s = math.sin(phase)
        if square:
            s = 0.6 if s >= 0 else -0.6
        out.append(s * math.exp(-decay * t) * min(1.0, i / attack) * vol)
    return out


def _noise(dur, vol=0.5, decay=5.0, smooth=1.0):
    n = max(1, int(RATE * dur))
    out = []
    y = 0.0
    for i in range(n):
        y += smooth * (random.uniform(-1, 1) - y)
        out.append(y * math.exp(-decay * i / n) * vol)
    return out


def _mix(*parts):
    out = [0.0] * max(len(p) for p in parts)
    for p in parts:
        for i, s in enumerate(p):
            out[i] += s
    return out


def _seq(parts):
    out = []
    for p in parts:
        out += p
    return out


def _notes(freqs, dur, vol=0.35, decay=2.0):
    return _seq([_tone(f, f, dur, vol, decay=decay) for f in freqs])


# имя -> функция, создающая отсчёты
RECIPES = {
    'shoot_cannon': lambda: _mix(_tone(900, 250, 0.07, 0.35, decay=5),
                                 _noise(0.03, 0.15, 8)),
    'shoot_sniper': lambda: _mix(_tone(1500, 180, 0.18, 0.4, decay=4),
                                 _noise(0.06, 0.25, 8)),
    'shoot_ice': lambda: _tone(1900, 1300, 0.12, 0.28, decay=3),
    'shoot_mortar': lambda: _mix(_tone(220, 70, 0.2, 0.55, decay=4),
                                 _noise(0.08, 0.2, 6, 0.3)),
    'explode': lambda: _noise(0.35, 0.8, 5, 0.12),
    'kill': lambda: _tone(650, 1100, 0.08, 0.3, decay=5),
    'leak': lambda: _tone(200, 80, 0.3, 0.4, square=True, decay=3),
    'wave': lambda: _seq([_tone(330, 330, 0.14, 0.4, decay=1.5),
                          _tone(440, 440, 0.2, 0.4, decay=2)]),
    'wave_clear': lambda: _notes((523, 659, 784), 0.09),
    'build': lambda: _mix(_tone(450, 700, 0.09, 0.35, decay=4),
                          _noise(0.03, 0.2, 8)),
    'upgrade': lambda: _notes((440, 554, 659, 880), 0.07),
    'sell': lambda: _seq([_tone(1200, 1200, 0.05, 0.3, decay=2),
                          _tone(1700, 1700, 0.1, 0.3, decay=3)]),
    'deny': lambda: _tone(160, 150, 0.14, 0.3, square=True, decay=2),
    'heal': lambda: _tone(700, 950, 0.15, 0.15, decay=3),
    'gameover': lambda: _notes((440, 392, 330, 247), 0.22, 0.45, 1.5),
    'victory': lambda: _notes((523, 659, 784), 0.14, 0.45, 1.0)
    + _tone(1047, 1047, 0.5, 0.45, decay=2),
}

# сколько копий звука держать (для быстрых повторов)
POOL = {'shoot_cannon': 3, 'shoot_sniper': 2, 'shoot_ice': 2,
        'shoot_mortar': 2, 'explode': 3, 'kill': 3}
# минимальная пауза между повторами одного звука, секунд
GAP = {'shoot_cannon': 0.06, 'shoot_sniper': 0.06, 'shoot_ice': 0.06,
       'shoot_mortar': 0.06, 'explode': 0.1, 'kill': 0.05, 'heal': 0.4,
       'leak': 0.15}
VOLUME = {'shoot_cannon': 0.5, 'shoot_sniper': 0.6, 'shoot_ice': 0.5,
          'shoot_mortar': 0.7, 'kill': 0.6, 'heal': 0.5}


def _write_wav(path, samples):
    frames = b''.join(struct.pack('<h', int(max(-1.0, min(1.0, s)) * 30000))
                      for s in samples)
    tmp = path + '.tmp'
    with wave.open(tmp, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(frames)
    os.replace(tmp, path)


class Sfx:
    def __init__(self):
        self.enabled = True
        self.ready = False
        self.folder = None
        self.files_done = False
        self.failed = False
        self.sounds = {}
        self.index = {}
        self.last = {}

    def _path(self, name):
        return os.path.join(self.folder, '%s_%s.wav' % (VERSION, name))

    def init(self, folder):
        """Запустить генерацию в фоне, затем загрузить звуки."""
        from kivy.clock import Clock
        self.folder = folder
        threading.Thread(target=self._generate, daemon=True).start()
        Clock.schedule_interval(self._poll, 0.4)

    def _generate(self):
        try:
            os.makedirs(self.folder, exist_ok=True)
            for name, make in RECIPES.items():
                path = self._path(name)
                if not os.path.exists(path):
                    _write_wav(path, make())
            self.files_done = True
        except Exception:
            self.failed = True

    def _poll(self, dt):
        """Вызывается таймером Kivy; True/None — продолжать, False — стоп."""
        if self.failed:
            return False
        if not self.files_done:
            return True
        try:
            self._load()
        except Exception:
            self.ready = False
        return False

    def _load(self):
        from kivy.core.audio import SoundLoader
        for name in RECIPES:
            pool = []
            for _ in range(POOL.get(name, 1)):
                snd = SoundLoader.load(self._path(name))
                if snd:
                    snd.volume = VOLUME.get(name, 0.8)
                    pool.append(snd)
            if pool:
                self.sounds[name] = pool
        self.ready = bool(self.sounds)

    def play(self, name):
        if not (self.enabled and self.ready):
            return
        pool = self.sounds.get(name)
        if not pool:
            return
        now = time.monotonic()
        if now - self.last.get(name, 0.0) < GAP.get(name, 0.0):
            return
        self.last[name] = now
        i = self.index.get(name, 0)
        self.index[name] = (i + 1) % len(pool)
        try:
            pool[i].play()
        except Exception:
            pass


SFX = Sfx()
