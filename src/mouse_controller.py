import ctypes
import sys
import time
from ctypes import wintypes
from typing import Callable, Optional, Tuple

from src.logger import get_logger

log = get_logger("mouse")

IS_WINDOWS = sys.platform == "win32"

# Win32 constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
VK_ESCAPE = 0x1B

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

user32 = ctypes.WinDLL("user32", use_last_error=True) if IS_WINDOWS else None


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


if IS_WINDOWS:
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    user32.GetSystemMetrics.restype = ctypes.c_int


def enable_dpi_awareness() -> bool:
    """
    Opts the process into per-monitor DPI awareness v2.

    Without this, Windows virtualises coordinates for the process on scaled
    displays, so a SetCursorPos target no longer matches the pixels the user
    actually sees. Must run before any window is created.
    """
    if not IS_WINDOWS:
        return False
    try:
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            if user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
                return True
        # Windows 8.1 fallback
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        return shcore.SetProcessDpiAwareness(2) == 0
    except (OSError, AttributeError) as e:
        log.warning("Could not enable DPI awareness: %s", e)
        return False


def precise_sleep(seconds: float) -> None:
    """
    Waits for `seconds` with sub-millisecond accuracy.

    time.sleep cannot resolve the 0.1-2.5ms delays the speed slider asks for,
    so short waits spin on the performance counter instead; that is what made
    actual drawing speed diverge from the estimate at the fast end.
    """
    if seconds <= 0:
        return
    if seconds > 0.002:
        time.sleep(seconds)
        return
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        pass


class TimerResolution:
    """Context manager raising the system timer resolution to 1ms while drawing."""

    def __init__(self):
        self._winmm = None

    def __enter__(self):
        if IS_WINDOWS:
            try:
                self._winmm = ctypes.WinDLL("winmm")
                self._winmm.timeBeginPeriod(1)
            except OSError:
                self._winmm = None
        return self

    def __exit__(self, *exc):
        if self._winmm is not None:
            try:
                self._winmm.timeEndPeriod(1)
            except OSError:
                pass
            self._winmm = None
        return False


class MouseController:
    """Controls native Windows mouse actions using Win32 API with safety mechanisms."""

    def __init__(self):
        self._is_pressed = False
        self._esc_listener = None
        self._esc_callback: Optional[Callable[[], None]] = None

    # ---------------- emergency stop ----------------

    def start_esc_listener(self, on_esc_callback: Callable[[], None]) -> None:
        """Starts a global keyboard listener to detect ESC press anywhere on the system."""
        self._esc_callback = on_esc_callback
        self.stop_esc_listener()

        try:
            import pynput.keyboard as pynput_keyboard
        except ImportError as e:
            # GetAsyncKeyState polling in the drawing loop still covers ESC.
            log.warning("pynput unavailable, relying on polled ESC only: %s", e)
            return

        def on_press(key):
            if key == pynput_keyboard.Key.esc:
                log.info("Emergency ESC detected")
                self.release_left_button()
                if self._esc_callback:
                    self._esc_callback()

        self._esc_listener = pynput_keyboard.Listener(on_press=on_press)
        self._esc_listener.daemon = True
        self._esc_listener.start()

    def stop_esc_listener(self) -> None:
        """Stops the global ESC listener."""
        if self._esc_listener is not None:
            try:
                self._esc_listener.stop()
            except Exception:  # pynput raises various backend errors on teardown
                pass
        self._esc_listener = None

    @staticmethod
    def check_esc_pressed() -> bool:
        """Direct Win32 API check to see if ESC key is currently down."""
        if not IS_WINDOWS:
            return False
        return bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)

    # ---------------- geometry ----------------

    @staticmethod
    def get_cursor_pos() -> Tuple[int, int]:
        """Returns the cursor position in physical screen pixels."""
        if not IS_WINDOWS:
            return (0, 0)
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return (int(point.x), int(point.y))

    @staticmethod
    def virtual_screen_rect() -> Tuple[int, int, int, int]:
        """Returns (left, top, width, height) of the whole virtual desktop."""
        if not IS_WINDOWS:
            return (0, 0, 1920, 1080)
        return (
            user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            max(1, user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)),
            max(1, user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)),
        )

    # ---------------- actions ----------------

    @staticmethod
    def _send(flags: int, dx: int = 0, dy: int = 0) -> None:
        if not IS_WINDOWS:
            return
        event = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=None))
        sent = user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))
        if sent != 1:
            log.error("SendInput rejected (flags=0x%X, error=%s)", flags, ctypes.get_last_error())

    @classmethod
    def move_to(cls, x: int, y: int) -> None:
        """
        Moves the cursor to an absolute physical screen position.

        The absolute coordinates are normalised over the *virtual* desktop:
        normalising over SM_CXSCREEN (the primary monitor) sent the pointer to
        the wrong place on any secondary monitor.
        """
        if not IS_WINDOWS:
            return
        ix, iy = int(x), int(y)

        # SendInput first so apps reading raw input see a genuine move event,
        # then SetCursorPos, because normalising to the 0..65535 absolute grid
        # rounds to within a pixel and SetCursorPos lands exactly.
        left, top, width, height = cls.virtual_screen_rect()
        norm_x = int(round((ix - left) * 65535 / width))
        norm_y = int(round((iy - top) * 65535 / height))
        cls._send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, norm_x, norm_y)

        user32.SetCursorPos(ix, iy)

    def press_left_button(self) -> None:
        """Presses left mouse button."""
        self._send(MOUSEEVENTF_LEFTDOWN)
        self._is_pressed = True

    def release_left_button(self) -> None:
        """Releases left mouse button."""
        self._send(MOUSEEVENTF_LEFTUP)
        self._is_pressed = False

    @property
    def is_pressed(self) -> bool:
        return self._is_pressed

    def safe_reset(self) -> None:
        """Emergency reset to ensure mouse button is released."""
        try:
            self.release_left_button()
        except Exception:
            log.exception("Failed to release mouse button during reset")
        self.stop_esc_listener()
