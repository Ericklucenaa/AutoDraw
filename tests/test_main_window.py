"""Behaviour of the main window: debouncing, staleness, persistence, teardown."""
import cv2
import pytest
from PySide6.QtWidgets import QMessageBox

from src.config import ConfigManager
from src.ui.main_window import MainWindow


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """A main window whose config lives in a temp dir and which never shows modals."""
    monkeypatch.setattr(
        "src.ui.main_window.ConfigManager", lambda: ConfigManager(base_dir=tmp_path)
    )
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    win = MainWindow()
    yield win
    win.close()


@pytest.fixture
def image_path(tmp_path, sample_bgr):
    path = tmp_path / "drawing.png"
    cv2.imwrite(str(path), sample_bgr)
    return str(path)


def _settle(qapp, window, timeout_ms=30000):
    """Fires the pending debounce and waits for the processing worker to finish."""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop, QTimer

    if window._recalc_timer.isActive():
        window._recalc_timer.stop()
        window._start_processing()

    worker = window.processor_worker
    if worker is None:
        return

    loop = QEventLoop()
    worker.finished.connect(loop.quit)
    QTimer.singleShot(timeout_ms, loop.quit)
    if worker.isRunning():
        loop.exec()
    worker.wait(QDeadlineTimer(timeout_ms))
    qapp.processEvents()


# ---------------- construction ----------------

def test_window_starts_with_drawing_disabled(window):
    assert window.btn_draw.isEnabled() is False
    assert window.processed_strokes == []


def test_window_restores_saved_settings(qapp, tmp_path, monkeypatch):
    config = ConfigManager(base_dir=tmp_path)
    config.set_many({
        "quality_level": "alta", "mode": "bw", "aspect_mode": "stretch",
        "speed": 77, "simplify_image": True,
    })
    monkeypatch.setattr(
        "src.ui.main_window.ConfigManager", lambda: ConfigManager(base_dir=tmp_path)
    )

    win = MainWindow()
    try:
        assert win._current_quality() == "alta"
        assert win._current_mode() == "bw"
        assert win._current_aspect_mode() == "stretch"
        assert win.slider_speed.value() == 77
        assert win.chk_simplify.isChecked() is True
    finally:
        win.close()


def test_restoring_settings_does_not_queue_work(qapp, tmp_path, monkeypatch):
    """Programmatic widget updates must not look like user edits."""
    monkeypatch.setattr(
        "src.ui.main_window.ConfigManager", lambda: ConfigManager(base_dir=tmp_path)
    )
    win = MainWindow()
    try:
        assert win._recalc_timer.isActive() is False
    finally:
        win.close()


# ---------------- loading ----------------

def test_loading_an_image_schedules_processing(window, image_path):
    window._load_image_from_path(image_path)
    assert window.current_image_info is not None
    assert image_path in window.config_manager.get("recent_images")


def test_failed_load_leaves_the_state_untouched(window, tmp_path):
    window._load_image_from_path(str(tmp_path / "missing.png"))
    assert window.current_image_info is None
    assert window.config_manager.get("recent_images") == []


def test_drawing_becomes_available_once_strokes_exist(qapp, window, image_path):
    window._on_area_selected(50, 60, 260, 200)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    assert window.processed_strokes
    assert window.total_points > 0
    assert window.estimated_seconds > 0
    assert window.btn_draw.isEnabled() is True


# ---------------- area selection ----------------

def test_selected_area_is_persisted(window):
    window._on_area_selected(10, 20, 300, 200)
    assert window.config_manager.get("last_area") == {"x": 10, "y": 20, "w": 300, "h": 200}
    assert "300×200" in window.lbl_area_status.text()
    assert window.lbl_area_status.objectName() == "BadgeSuccess"


# ---------------- debouncing & staleness ----------------

def test_option_changes_are_coalesced_into_one_pass(qapp, window, image_path, monkeypatch):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    starts = []
    monkeypatch.setattr(window, "_start_processing", lambda: starts.append(1))

    for value in range(30, 90):
        window.slider_speed.setValue(value)
    window.cmb_quality.setCurrentIndex(0)
    window.chk_simplify.setChecked(True)

    # Nothing runs until the debounce timer fires.
    assert starts == []
    assert window._recalc_timer.isActive()
    window._recalc_timer.stop()
    window._recalc_timer.timeout.emit()
    assert len(starts) == 1


def test_speed_changes_do_not_reprocess(qapp, window, image_path, monkeypatch):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    before = window.estimated_seconds
    strokes_before = window.processed_strokes

    starts = []
    monkeypatch.setattr(window, "_start_processing", lambda: starts.append(1))
    window.slider_speed.setValue(100)

    assert starts == [], "speed does not change geometry, so nothing should reprocess"
    assert window._recalc_timer.isActive() is False
    assert window.processed_strokes is strokes_before
    assert window.estimated_seconds < before, "a faster speed must shorten the estimate"


def test_geometry_changes_clear_stale_strokes(qapp, window, image_path):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)
    assert window.btn_draw.isEnabled()

    window.cmb_quality.setCurrentIndex(0)
    assert window.processed_strokes == []
    assert window.btn_draw.isEnabled() is False, "cannot draw with outdated geometry"


def test_results_from_a_superseded_pass_are_ignored(qapp, window, image_path):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    current_id = window._active_request_id
    window._on_processing_finished([[(0, 0), (1, 1)]], 999.0, 2, current_id - 1)

    assert window.estimated_seconds != 999.0


def test_errors_from_a_superseded_pass_are_ignored(qapp, window, image_path):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    summary = window.lbl_trajectory_summary.text()
    window._on_processing_error("stale failure", window._active_request_id - 1)
    assert window.lbl_trajectory_summary.text() == summary


def test_processing_error_surfaces_and_disables_drawing(qapp, window, image_path):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    window._on_processing_error("boom", window._active_request_id)
    assert window.processed_strokes == []
    assert window.btn_draw.isEnabled() is False
    assert "Falha" in window.lbl_trajectory_summary.text()


# ---------------- volume warning ----------------

def test_volume_warning_appears_above_the_threshold(qapp, window, image_path):
    window.config_manager.set("warn_above_points", 10)
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    assert window.lbl_volume_warning.isVisible() or window.lbl_volume_warning.isVisibleTo(window)
    assert "pontos" in window.lbl_volume_warning.text()


def test_volume_warning_hidden_when_disabled(qapp, window, image_path):
    window.config_manager.set("warn_above_points", 0)
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    assert window.lbl_volume_warning.isVisibleTo(window) is False


def test_long_drawing_confirmation_respects_the_answer(window, monkeypatch):
    window.total_points = 10_000
    window.config_manager.set("warn_above_points", 100)

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
    )
    assert window._confirm_long_drawing() is False

    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )
    assert window._confirm_long_drawing() is True


def test_short_drawings_skip_the_confirmation(window):
    window.total_points = 10
    window.config_manager.set("warn_above_points", 1000)
    assert window._confirm_long_drawing() is True


# ---------------- persistence ----------------

def test_drawing_settings_are_persisted(window):
    window.cmb_quality.setCurrentIndex(2)
    window.cmb_mode.setCurrentIndex(1)
    window.radio_aspect_stretch.setChecked(True)
    window.slider_speed.setValue(88)
    window.chk_simplify.setChecked(True)

    window._persist_drawing_settings()

    reloaded = ConfigManager(base_dir=window.config_manager.app_dir)
    assert reloaded.get("quality_level") == "alta"
    assert reloaded.get("mode") == "bw"
    assert reloaded.get("aspect_mode") == "stretch"
    assert reloaded.get("speed") == 88
    assert reloaded.get("simplify_image") is True


def test_pending_settings_are_flushed_on_close(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.ui.main_window.ConfigManager", lambda: ConfigManager(base_dir=tmp_path)
    )
    win = MainWindow()
    win.slider_speed.setValue(93)
    assert win._settings_save_timer.isActive()

    win.close()

    assert ConfigManager(base_dir=tmp_path).get("speed") == 93


# ---------------- teardown ----------------

def test_closing_stops_the_drawing_worker(qapp, window, image_path, monkeypatch):
    window._on_area_selected(0, 0, 200, 160)
    window._load_image_from_path(image_path)
    _settle(qapp, window)

    calls = {"stop": 0, "reset": 0}

    class FakeWorker:
        mouse = type("M", (), {"safe_reset": lambda self: calls.__setitem__("reset", 1)})()

        def isRunning(self):
            return True

        def stop(self):
            calls["stop"] += 1

        def wait(self, _ms):
            return True

    window.drawing_worker = FakeWorker()
    window.close()

    assert calls["stop"] == 1
    assert calls["reset"] == 1


def test_closing_cancels_a_running_processing_pass(qapp, window, image_path):
    window._on_area_selected(0, 0, 600, 500)
    window._load_image_from_path(image_path)
    window._recalc_timer.stop()
    window._start_processing()

    worker = window.processor_worker
    window.close()

    assert worker.is_cancelled is True
    worker.wait(30000)


def test_repeat_goes_through_the_countdown(window, monkeypatch):
    """Repeating must never take the mouse over without warning the user."""
    calls = []
    monkeypatch.setattr(window, "_execute_drawing", lambda: calls.append("draw"))
    monkeypatch.setattr(
        "src.ui.main_window.CountdownOverlayDialog",
        lambda countdown_sec, parent: type("D", (), {"exec": lambda self: 1})(),
    )

    window._run_countdown_then_draw()
    assert calls == ["draw"]


def test_cancelled_countdown_does_not_draw(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "_execute_drawing", lambda: calls.append("draw"))
    monkeypatch.setattr(
        "src.ui.main_window.CountdownOverlayDialog",
        lambda countdown_sec, parent: type("D", (), {"exec": lambda self: 0})(),
    )

    window._run_countdown_then_draw()
    assert calls == []


# ---------------- preview tabs ----------------

@pytest.mark.parametrize("mode", ["processed", "original", "area"])
def test_preview_tabs_are_mutually_exclusive(window, mode):
    window._set_preview_mode(mode)
    assert window.preview_canvas.view_mode == mode
    assert [name for name, b in window.preview_tabs.items() if b.isChecked()] == [mode]


def test_drop_of_an_unsupported_file_is_rejected(window, qapp, tmp_path):
    from PySide6.QtCore import QMimeData, QPoint, QUrl
    from PySide6.QtGui import QDropEvent
    from PySide6.QtCore import Qt

    path = tmp_path / "notes.txt"
    path.write_text("hi", encoding="utf-8")

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    event = QDropEvent(
        QPoint(10, 10), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )

    window.dropEvent(event)
    assert window.current_image_info is None


def test_drop_of_a_supported_file_loads_it(window, image_path):
    from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
    from PySide6.QtGui import QDropEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(image_path)])
    event = QDropEvent(
        QPoint(10, 10), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )

    window.dropEvent(event)
    assert window.current_image_info is not None
    assert window.current_image_info.filename == "drawing.png"
