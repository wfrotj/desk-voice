"""Play voice messages sent from the phone. Listens only on this computer."""

from __future__ import annotations

import array
import logging
import math
import os
import queue
import struct
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import winsound

ROOT = Path(__file__).resolve().parent


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be a whole number")
    if value < 1:
        raise SystemExit(f"{name} must be at least 1")
    return value


load_env(ROOT / ".env")
HOST = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = env_int("PORT", 8787)
MAX_BYTES = env_int("MAX_BYTES", 8 * 1024 * 1024)
MAX_SECONDS = env_int("MAX_SECONDS", 60)
STATIC = {
    "/manifest.webmanifest": (ROOT / "manifest.webmanifest", "application/manifest+json"),
    "/sw.js": (ROOT / "sw.js", "text/javascript; charset=utf-8"),
    "/icon-180.png": (ROOT / "icon-180.png", "image/png"),
    "/icon-192.png": (ROOT / "icon-192.png", "image/png"),
    "/icon-512.png": (ROOT / "icon-512.png", "image/png"),
    "/apple-touch-icon.png": (ROOT / "icon-180.png", "image/png"),
    "/apple-touch-icon-precomposed.png": (ROOT / "icon-180.png", "image/png"),
    "/favicon.ico": (ROOT / "icon-180.png", "image/png"),
}
PID_PATH = ROOT / "voice-receiver.pid"
LOG_PATH = ROOT / "voice-receiver.log"

play_queue: queue.Queue[Path] = queue.Queue()


def player() -> None:
    while True:
        path = play_queue.get()
        try:
            winsound.PlaySound(str(path), winsound.SND_FILENAME)
        except Exception:
            logging.exception("playback failed")
        finally:
            path.unlink(missing_ok=True)
            play_queue.task_done()


def wav_bytes(rate: int, samples: bytes) -> bytes:
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(samples),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        rate,
        rate * 2,
        2,
        16,
        b"data",
        len(samples),
    )
    return header + samples


def make_beep() -> Path:
    rate = 22050
    freq = 880
    count = int(rate * 0.28)
    frames = bytearray()
    for index in range(count):
        fade = min(1.0, index / 180, (count - index) / 180)
        value = int(9000 * fade * math.sin(2 * math.pi * freq * index / rate))
        frames += struct.pack("<h", value)
    handle, name = tempfile.mkstemp(suffix=".wav", prefix="beep-")
    os.close(handle)
    path = Path(name)
    path.write_bytes(wav_bytes(rate, bytes(frames)))
    return path


RATE = 22050


def clamp_sample(value: float) -> int:
    return max(-32767, min(32767, int(value)))


def make_siren() -> array.array:
    count = int(RATE * 2.6)
    samples = array.array("h")
    phase = 0.0
    freq = 660.0
    for index in range(count):
        slot = (index / RATE) % 0.84
        target = 640.0 if slot < 0.42 else 880.0
        freq += (target - freq) * 0.14
        phase += 2 * math.pi * freq / RATE
        edge = min(1.0, index / 280, (count - index) / 900)
        samples.append(clamp_sample(15000 * edge * math.sin(phase)))
    return samples


def make_knock() -> array.array:
    count = int(RATE * 0.82)
    samples = array.array("h", [0] * count)

    def hit(start: int) -> None:
        length = int(RATE * 0.16)
        for index in range(length):
            pos = start + index
            if pos >= count:
                break
            t = index / RATE
            noise = math.sin(index * 12.9898) * math.sin(index * 78.233)
            click = noise * math.exp(-t * 70)
            body = math.sin(2 * math.pi * 92 * t) * math.exp(-t * 14)
            wood = math.sin(2 * math.pi * 210 * t) * math.exp(-t * 26)
            mixed = 19000 * (0.45 * click + 0.9 * body + 0.4 * wood)
            samples[pos] = clamp_sample(samples[pos] + mixed)

    hit(int(RATE * 0.02))
    hit(int(RATE * 0.38))
    return samples


SIREN = make_siren()
KNOCK = make_knock()


def queue_samples(samples: array.array, prefix: str) -> None:
    queue_wav(wav_bytes(RATE, samples.tobytes()), prefix)


def queue_wav(data: bytes, prefix: str) -> None:
    handle, name = tempfile.mkstemp(suffix=".wav", prefix=prefix)
    os.close(handle)
    path = Path(name)
    path.write_bytes(data)
    play_queue.put(path)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        logging.info("%s - " + fmt, self.address_string(), *args)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            page = (ROOT / "index.html").read_text(encoding="utf-8")
            page = page.replace("__MAX_SECONDS__", str(MAX_SECONDS))
            self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
            return
        if path == "/health":
            self._send(200, "application/json", b'{"ok":true}')
            return
        item = STATIC.get(path)
        if item and item[0].is_file():
            self._send(200, item[1], item[0].read_bytes())
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > MAX_BYTES:
            self._json(413, ok=False, error="That message is too long.")
            return
        data = self.rfile.read(length) if length else b""

        if path == "/beep":
            play_queue.put(make_beep())
            self._json(200, ok=True)
            return

        if path == "/siren":
            queue_samples(SIREN, "siren-")
            logging.info("queued siren")
            self._json(200, ok=True)
            return

        if path == "/knock":
            queue_samples(KNOCK, "knock-")
            logging.info("queued knock")
            self._json(200, ok=True)
            return

        if path == "/play":
            if len(data) < 44 or not data.startswith(b"RIFF"):
                self._json(400, ok=False, error="The recording could not be read.")
                return
            queue_wav(data, "voice-")
            logging.info("queued voice message (%s bytes)", len(data))
            self._json(200, ok=True)
            return

        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def _json(self, status: int, ok: bool, error: str | None = None) -> None:
        if error:
            body = ('{"ok":false,"error":"%s"}' % error.replace('"', "'")).encode()
        else:
            body = b'{"ok":true}' if ok else b'{"ok":false}'
        self._send(status, "application/json", body)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    threading.Thread(target=player, name="player", daemon=True).start()
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        logging.error("port %s is already in use", PORT)
        return
    PID_PATH.write_text(str(os.getpid()), encoding="ascii")
    logging.info("voice receiver listening on %s:%s", HOST, PORT)
    try:
        server.serve_forever()
    finally:
        PID_PATH.unlink(missing_ok=True)
        server.server_close()


if __name__ == "__main__":
    main()
