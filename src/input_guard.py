"""
Detects the *user* touching the mouse while AutoDraw is drawing.

Windows Raw Input tells injected events apart from real ones: an event sent
with SendInput (what the drawing engine does) arrives with hDevice == NULL,
while a physical mouse, touchpad or tablet always carries its device handle.
Raw input is buffered and read on the UI thread, so unlike a low-level mouse
hook it never sits in the input pipeline and cannot slow the drawing down.

Only the Windows code paths touch user32; on other platforms start() simply
returns False, so the module stays importable for the test suite.
"""
import ctypes
import sys
import time
from collections import deque
from ctypes import wintypes
from typing import Callable, Deque, Optional, Tuple

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

from src.logger import get_logger

log = get_logger("guard")

IS_WINDOWS = sys.platform == "win32"

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE = 0x00000001
MOUSE_MOVE_ABSOLUTE = 0x01
# Button-down flags (left, right, middle, X1, X2).
BUTTON_DOWN_FLAGS = 0x0001 | 0x0004 | 0x0010 | 0x0040 | 0x0100

# Real movement, in mouse counts, tolerated within WINDOW_SEC before the guard
# fires: enough to ignore a bump on the desk, far less than a deliberate move.
DEFAULT_MOVE_THRESHOLD = 40
WINDOW_SEC = 1.0
# An absolute device (pen tablet, remote desktop) reports positions, not
# deltas; each real event of that kind counts as this much movement.
ABSOLUTE_EVENT_WEIGHT = 10


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class _BUTTONS(ctypes.Structure):
    _fields_ = [("usButtonFlags", wintypes.USHORT), ("usButtonData", wintypes.USHORT)]


class _BUTTONS_UNION(ctypes.Union):
    _anonymous_ = ("s",)
    _fields_ = [("ulButtons", wintypes.ULONG), ("s", _BUTTONS)]


class RAWMOUSE(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("u", _BUTTONS_UNION),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT_MOUSE(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.RegisterRawInputDevices.argtypes = (ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT)
    _user32.RegisterRawInputDevices.restype = wintypes.BOOL
    _user32.GetRawInputData.argtypes = (
        wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT), wintypes.UINT,
    )
    _user32.GetRawInputData.restype = wintypes.UINT
else:  # pragma: no cover
    _user32 = None


class MovementMeter:
    """Sliding-window sum of real mouse movement (pure logic, unit tested)."""

    def __init__(self, threshold: int = DEFAULT_MOVE_THRESHOLD, window_sec: float = WINDOW_SEC):
        self.threshold = threshold
        self.window_sec = window_sec
        self._samples: Deque[Tuple[float, int]] = deque()
        self._total = 0

    def reset(self) -> None:
        self._samples.clear()
        self._total = 0

    def add(self, amount: int, now: Optional[float] = None) -> bool:
        """Records movement; returns True once the window total crosses the threshold."""
        now = time.monotonic() if now is None else now
        self._samples.append((now, amount))
        self._total += amount
        while self._samples and now - self._samples[0][0] > self.window_sec:
            self._total -= self._samples.popleft()[1]
        return self._total >= self.threshold


class RealMouseGuard(QAbstractNativeEventFilter):
    """
    Calls on_touch(reason) when the user really moves or clicks the mouse.

    Use suspend()/resume() around moments where the user is expected to use
    the mouse (the drawing is paused and they head for the Continue button).
    """

    def __init__(self, on_touch: Callable[[str], None], move_threshold: int = DEFAULT_MOVE_THRESHOLD):
        super().__init__()
        self._on_touch = on_touch
        self._meter = MovementMeter(move_threshold)
        self._active = False
        self._suspended = False
        self._grace_until = 0.0
        self._fired = False

    # ---------------- lifecycle ----------------

    def start(self, hwnd: int) -> bool:
        """Registers for raw mouse input delivered to hwnd, even in the background."""
        if not IS_WINDOWS or self._active:
            return False
        device = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, wintypes.HWND(int(hwnd)))
        if not _user32.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(RAWINPUTDEVICE)):
            log.warning("RegisterRawInputDevices failed (error %s)", ctypes.get_last_error())
            return False
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)
        self._active = True
        self._fired = False
        self._meter.reset()
        log.info("Real-mouse guard active")
        return True

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        app = QCoreApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)
        device = RAWINPUTDEVICE(0x01, 0x02, RIDEV_REMOVE, None)
        _user32.RegisterRawInputDevices(ctypes.byref(device), 1, ctypes.sizeof(RAWINPUTDEVICE))

    def suspend(self) -> None:
        self._suspended = True

    def resume(self, grace_sec: float = 1.0) -> None:
        """Re-arms the guard, ignoring input for grace_sec while the hand leaves the mouse."""
        self._meter.reset()
        self._grace_until = time.monotonic() + grace_sec
        self._fired = False
        self._suspended = False

    # ---------------- detection ----------------

    def feed(self, is_real: bool, button_down: bool, movement: int) -> None:
        """Feeds one decoded mouse event (split out so it can be unit tested)."""
        if not is_real or self._suspended or self._fired:
            return
        if time.monotonic() < self._grace_until:
            return
        if button_down:
            self._fire("clique do mouse")
        elif movement and self._meter.add(movement):
            self._fire("mouse mexido")

    def _fire(self, reason: str) -> None:
        self._fired = True
        log.info("Real mouse input detected: %s", reason)
        try:
            self._on_touch(reason)
        except Exception:
            log.exception("Guard callback failed")

    def nativeEventFilter(self, eventType, message):
        if not self._active:
            return False, 0
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_INPUT:
                self._handle_raw(msg.lParam)
        except Exception:
            log.debug("Raw input decode failed", exc_info=True)
        return False, 0

    def _handle_raw(self, handle) -> None:
        data = RAWINPUT_MOUSE()
        size = wintypes.UINT(ctypes.sizeof(data))
        got = _user32.GetRawInputData(
            wintypes.HANDLE(handle), RID_INPUT, ctypes.byref(data), ctypes.byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )
        if got in (0, 0xFFFFFFFF) or data.header.dwType != RIM_TYPEMOUSE:
            return
        mouse = data.mouse
        if mouse.usFlags & MOUSE_MOVE_ABSOLUTE:
            movement = ABSOLUTE_EVENT_WEIGHT
        else:
            movement = abs(mouse.lLastX) + abs(mouse.lLastY)
        self.feed(
            is_real=bool(data.header.hDevice),
            button_down=bool(mouse.usButtonFlags & BUTTON_DOWN_FLAGS),
            movement=movement,
        )
