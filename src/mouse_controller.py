import time
import ctypes
from ctypes import wintypes
from typing import Optional, Callable
import pynput.keyboard as pynput_keyboard

# Win32 Constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
VK_ESCAPE = 0x1B

user32 = ctypes.windll.user32


class MouseController:
    """Controls native Windows mouse actions using Win32 API with safety mechanisms."""

    def __init__(self):
        self._is_pressed = False
        self._esc_listener: Optional[pynput_keyboard.Listener] = None
        self._esc_callback: Optional[Callable[[], None]] = None

    def start_esc_listener(self, on_esc_callback: Callable[[], None]) -> None:
        """Starts a global keyboard listener to detect ESC press anywhere on the system."""
        self._esc_callback = on_esc_callback

        def on_press(key):
            if key == pynput_keyboard.Key.esc:
                print("[MouseController] EMERGENCY ESC KEY DETECTED!")
                self.release_left_button()
                if self._esc_callback:
                    self._esc_callback()

        self.stop_esc_listener()
        self._esc_listener = pynput_keyboard.Listener(on_press=on_press)
        self._esc_listener.daemon = True
        self._esc_listener.start()

    def stop_esc_listener(self) -> None:
        """Stops the global ESC listener."""
        if self._esc_listener and self._esc_listener.is_alive():
            try:
                self._esc_listener.stop()
            except Exception:
                pass
        self._esc_listener = None

    @staticmethod
    def check_esc_pressed() -> bool:
        """Direct Win32 API check to see if ESC key is currently down."""
        state = user32.GetAsyncKeyState(VK_ESCAPE)
        return bool(state & 0x8000)

    @staticmethod
    def move_to(x: int, y: int) -> None:
        """Moves cursor to absolute screen position (x, y) and sends mouse move event."""
        ix, iy = int(x), int(y)
        user32.SetCursorPos(ix, iy)

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        if screen_w > 0 and screen_h > 0:
            norm_x = int((ix * 65535) / screen_w)
            norm_y = int((iy * 65535) / screen_h)
            user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, norm_x, norm_y, 0, 0)

    def press_left_button(self) -> None:
        """Presses left mouse button."""
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self._is_pressed = True

    def release_left_button(self) -> None:
        """Releases left mouse button."""
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self._is_pressed = False

    def safe_reset(self) -> None:
        """Emergency reset to ensure mouse button is released."""
        try:
            self.release_left_button()
        except Exception:
            pass
        self.stop_esc_listener()
