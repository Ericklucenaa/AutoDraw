"""Languages: every string is translated, placeholders survive, and switching works live."""
import ast
import re
import string
from pathlib import Path

import pytest

from src import i18n
from src.i18n import TRANSLATIONS, set_language, tr

SRC = Path(__file__).resolve().parent.parent / "src"


@pytest.fixture(autouse=True)
def _portuguese_after_each_test():
    yield
    set_language("pt")


def _source_keys():
    """Every literal passed to tr() in src/, plus the tutorial steps and runtime reasons."""
    keys = set()
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        consts = {
            t.id: n.value.value
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
            for t in n.targets if isinstance(t, ast.Name)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    keys.add(arg.value)
                elif isinstance(arg, ast.Name) and arg.id in consts:
                    keys.add(consts[arg.id])
    from src.ui.tutorial_dialog import STEPS
    from src.drawing_engine import ESC_REASON, STOP_REASON
    for _, title, text in STEPS:
        keys.update((title, text))
    keys.update(("Baixa", "Média", "Alta", "Contorno", "Preto e Branco", "mouse mexido", "clique do mouse",
                 "🎨 Resultado", "🖼️ Original", "📐 Simulação", ESC_REASON, STOP_REASON))
    return keys


def test_every_string_has_english_and_spanish():
    missing = sorted(k for k in _source_keys() if k not in TRANSLATIONS)
    assert not missing, f"untranslated: {missing}"


def _fields(text):
    return sorted({name for _, name, _, _ in string.Formatter().parse(text) if name})


@pytest.mark.parametrize("key", sorted(TRANSLATIONS))
def test_translations_keep_the_placeholders(key):
    en, es = TRANSLATIONS[key]
    assert _fields(en) == _fields(key), f"EN placeholders differ: {key!r}"
    assert _fields(es) == _fields(key), f"ES placeholders differ: {key!r}"
    assert en.strip() and es.strip()


def test_tr_translates_and_formats():
    assert tr("Traço: {current:,} / {total:,}", current=1200, total=5000) == "Traço: 1,200 / 5,000"
    set_language("en")
    assert tr("Traço: {current:,} / {total:,}", current=1200, total=5000) == "Stroke: 1,200 / 5,000"
    set_language("es")
    assert tr("▶ DESENHAR") == "▶ DIBUJAR"


def test_unknown_text_and_language_fall_back_to_portuguese():
    assert set_language("xx") == "pt"
    set_language("en")
    assert tr("texto que não existe") == "texto que não existe"


def test_detect_language_returns_a_shipped_language():
    assert i18n.detect_language() in i18n.LANGUAGES


def test_config_rejects_unknown_languages(tmp_path):
    from src.config import ConfigManager

    cfg = ConfigManager(base_dir=tmp_path)
    assert cfg.get("language") == ""
    (tmp_path / "config.json").write_text('{"language": "klingon"}', encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("language") == ""
    (tmp_path / "config.json").write_text('{"language": "es"}', encoding="utf-8")
    assert ConfigManager(base_dir=tmp_path).get("language") == "es"


def _texts(widget):
    from PySide6.QtWidgets import QLabel, QPushButton

    return [w.text() for cls in (QLabel, QPushButton) for w in widget.findChildren(cls) if w.text()]


def test_switching_language_rebuilds_the_window_in_place(window, image_path, qapp):
    window._on_area_selected(0, 0, 300, 200)
    window._load_image_from_path(image_path)

    window.cmb_language.setCurrentIndex(window.cmb_language.findData("en"))
    qapp.processEvents()

    texts = _texts(window)
    assert "▶ DRAW" in texts
    assert "📁 CHOOSE IMAGE" in texts
    assert window.windowTitle() == "AutoDraw — Automatic Drawer"
    assert window.config_manager.get("language") == "en"
    # The loaded image and the area survive the rebuild.
    assert window.current_image_info is not None
    assert "drawing.png" in window.lbl_image_info.text()
    assert "300×200" in window.lbl_area_status.text()

    window.cmb_language.setCurrentIndex(window.cmb_language.findData("es"))
    qapp.processEvents()
    assert "▶ DIBUJAR" in _texts(window)


def test_tutorial_walks_through_every_step(qapp):
    from src.ui.tutorial_dialog import STEPS, TutorialDialog

    dialog = TutorialDialog()
    seen = [dialog.lbl_title.text()]
    for _ in range(len(STEPS) - 1):
        dialog.btn_next.click()
        seen.append(dialog.lbl_title.text())
    assert seen == [title for _, title, _ in STEPS]
    assert re.search("✓", dialog.btn_next.text())
    dialog.btn_next.click()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_tutorial_is_shown_once(window, monkeypatch):
    shown = []
    monkeypatch.setattr("src.ui.main_window.TutorialDialog", lambda parent: type("D", (), {"exec": lambda self: shown.append(1)})())
    monkeypatch.setattr("src.ui.main_window.QTimer.singleShot", lambda _ms, fn: fn())
    window.config_manager.set("tutorial_seen", False)
    window.maybe_show_tutorial()
    window.maybe_show_tutorial()
    assert shown == [1]
    assert window.config_manager.get("tutorial_seen") is True
