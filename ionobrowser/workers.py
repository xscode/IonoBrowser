"""
IonoBrowser — background worker threads.

  DownloadWorker      — fetches a URL and returns raw bytes
  SDRWebSocketWorker  — SDRConnect WebSocket API
  RigctldWorker       — Hamlib rigctld TCP protocol (SDR++, GQRX)
"""

import ssl
import json
import asyncio
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

from .constants import APP_NAME, APP_VERSION

try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


# ── Download Worker ───────────────────────────────────────────────────────────

class DownloadWorker(QThread):
    finished = pyqtSignal(str, bytes, str)   # label, raw bytes, format_hint
    failed   = pyqtSignal(str, str)

    def __init__(self, label: str, url: str, fmt: str = ""):
        super().__init__()
        self.label = label
        self.url   = url
        self.fmt   = fmt

    def run(self):
        try:
            data = self._fetch()
            self.finished.emit(self.label, data, self.fmt)
        except Exception as e:
            self.failed.emit(self.label, str(e))

    def _fetch(self) -> bytes:
        headers = {"User-Agent": f"{APP_NAME}/{APP_VERSION}"}

        if REQUESTS_AVAILABLE:
            import warnings
            from requests.adapters import HTTPAdapter
            from urllib3.poolmanager import PoolManager

            class NoSNIAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    ctx.check_hostname = False
                    ctx.verify_mode    = ssl.CERT_NONE
                    _orig_wrap = ctx.wrap_socket
                    def _wrap_no_sni(sock, *a, **kw):
                        kw["server_hostname"] = None
                        return _orig_wrap(sock, *a, **kw)
                    ctx.wrap_socket = _wrap_no_sni
                    kwargs["ssl_context"] = ctx
                    self.poolmanager = PoolManager(*args, **kwargs)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                session = _requests.Session()
                session.mount("https://", NoSNIAdapter())
                resp = session.get(self.url, headers=headers, verify=False, timeout=30)
            resp.raise_for_status()
            return resp.content

        # Fallback: urllib with SNI suppressed
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        _orig_wrap = ctx.wrap_socket
        def _wrap_no_sni(sock, *a, **kw):
            kw["server_hostname"] = None
            return _orig_wrap(sock, *a, **kw)
        ctx.wrap_socket = _wrap_no_sni
        req = urllib.request.Request(self.url, headers=headers)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read()


# ── SDRConnect WebSocket Worker ───────────────────────────────────────────────

class SDRWebSocketWorker(QThread):
    connected       = pyqtSignal()
    disconnected    = pyqtSignal(str)
    property_update = pyqtSignal(str, str)
    error           = pyqtSignal(str)

    def __init__(self, host="localhost", port=8073):
        super().__init__()
        self.host     = host
        self.port     = port
        self._running = False
        self._ws      = None
        self._loop    = None
        self._send_queue: list = []

    @property
    def uri(self):
        return f"ws://{self.host}:{self.port}"

    def run(self):
        if not WEBSOCKETS_AVAILABLE:
            self.error.emit("websockets library not installed.\nRun: pip install websockets")
            return
        self._running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._loop.close()

    async def _connect(self):
        try:
            async with websockets.connect(self.uri) as ws:
                self._ws = ws
                self.connected.emit()
                for msg in self._send_queue:
                    await ws.send(msg)
                self._send_queue.clear()
                async for raw in ws:
                    if not self._running:
                        break
                    if isinstance(raw, str):
                        try:
                            msg = json.loads(raw)
                            et  = msg.get("event_type", "")
                            if et in ("property_changed", "get_property_response"):
                                self.property_update.emit(
                                    msg.get("property", ""), msg.get("value", "")
                                )
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            self.disconnected.emit(str(e))
        finally:
            self._ws = None

    def send(self, event_type: str, prop: str = "", value: str = ""):
        msg = json.dumps({"event_type": event_type, "property": prop, "value": value})
        if self._ws and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)
        else:
            self._send_queue.append(msg)

    def set_property(self, prop: str, value: str): self.send("set_property", prop, value)
    def get_property(self, prop: str):             self.send("get_property",  prop, "")

    def stop(self):
        self._running = False
        if self._ws and self._loop:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)


# ── Rigctld TCP Worker  (SDR++, GQRX) ────────────────────────────────────────

class RigctldWorker(QThread):
    """Connects to a Hamlib rigctld TCP server.

    Protocol is plain text over TCP:
      Send  "F <hz>\\n"          to set frequency
      Send  "f\\n"               to query frequency  → "<hz>\\n"
      Send  "M <mode> 0\\n"      to set mode
      Send  "m\\n"               to query mode       → "<mode>\\n" + "<passband>\\n"
      Send  "l STRENGTH\\n"      to query signal level (GQRX only)
    """
    connected       = pyqtSignal()
    disconnected    = pyqtSignal(str)
    property_update = pyqtSignal(str, str)
    error           = pyqtSignal(str)

    POLL_INTERVAL_S = 1.0
    SOCK_TIMEOUT_S  = 5.0   # per-recv timeout — must be > poll interval
    MAX_ERRORS      = 3     # consecutive poll failures before disconnecting

    def __init__(self, host="localhost", port=4532, strength_supported=False, mode_supported=True):
        super().__init__()
        self.host                = host
        self.port                = port
        self._running            = False
        self._sock               = None
        self._pending: list[str] = []
        self._strength_supported = strength_supported
        self._mode_supported     = mode_supported

    def set_frequency(self, freq_hz: int):
        self._send(f"F {freq_hz}\n")

    def set_mode(self, mode: str):
        mode_map = {
            "AM": "AM", "FM": "FM", "WFM": "WFM",
            "USB": "USB", "LSB": "LSB", "CW": "CW",
            "CWR": "CWR", "RTTY": "RTTY", "RTTYR": "RTTYR",
        }
        rigmode = mode_map.get(mode.upper(), "AM")
        self._send(f"M {rigmode} 0\n")

    def stop(self):
        self._running = False
        if self._sock:
            try: self._sock.close()
            except Exception: pass

    def _send(self, cmd: str):
        if self._sock:
            try: self._sock.sendall(cmd.encode())
            except Exception: pass
        else:
            self._pending.append(cmd)

    def _recv_line(self) -> str | None:
        buf = b""
        try:
            while True:
                ch = self._sock.recv(1)
                if not ch:
                    return None
                if ch == b"\n":
                    return buf.decode(errors="replace").strip()
                buf += ch
        except Exception:
            return None

    def run(self):
        import socket, time
        self._running = True
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=5)
            self._sock.settimeout(self.SOCK_TIMEOUT_S)
        except Exception as e:
            self.error.emit(f"Could not connect to {self.host}:{self.port}\n{e}")
            self._running = False
            return

        self.connected.emit()

        for cmd in self._pending:
            try: self._sock.sendall(cmd.encode())
            except Exception: pass
        self._pending.clear()

        last_poll    = 0.0
        error_count  = 0
        while self._running:
            now = time.monotonic()
            if now - last_poll >= self.POLL_INTERVAL_S:
                try:
                    # ── Frequency ────────────────────────────────────────
                    self._sock.sendall(b"f\n")
                    resp = self._recv_line()
                    if resp is None:
                        raise IOError("No response to 'f'")
                    if not resp.startswith("RPRT"):
                        try:
                            hz = int(float(resp))
                            self.property_update.emit("device_vfo_frequency", str(hz))
                        except ValueError:
                            pass

                    # ── Mode (two lines: mode name + passband Hz) ────────
                    if self._mode_supported:
                        self._sock.sendall(b"m\n")
                        line1 = self._recv_line()
                        line2 = self._recv_line()
                        if line1 is None or line2 is None:
                            raise IOError("No response to 'm'")
                        if not line1.startswith("RPRT"):
                            self.property_update.emit("demodulator", line1)

                    # ── Signal strength (GQRX only) ──────────────────────
                    if self._strength_supported:
                        self._sock.sendall(b"l STRENGTH\n")
                        strength_resp = self._recv_line()
                        if strength_resp is None:
                            raise IOError("No response to 'l STRENGTH'")
                        if not strength_resp.startswith("RPRT"):
                            try:
                                db = float(strength_resp)
                                self.property_update.emit("signal_power", f"{db:.1f}")
                            except ValueError:
                                pass

                    error_count = 0

                except Exception as e:
                    error_count += 1
                    self.error.emit(f"Poll error ({error_count}/{self.MAX_ERRORS}): {type(e).__name__}: {e}")
                    if error_count >= self.MAX_ERRORS:
                        break

                last_poll = now
            else:
                time.sleep(0.05)

        self._running = False
        self._sock    = None
        self.disconnected.emit("Connection closed")