import cv2
import numpy as np
import pytest

from src.image_loader import ImageLoader, ImageLoadError

SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
    '<rect x="2" y="2" width="{iw}" height="{ih}" fill="black"/></svg>'
)


def _write_svg(path, width, height):
    path.write_text(
        SVG_TEMPLATE.format(w=width, h=height, iw=max(1, width - 4), ih=max(1, height - 4)),
        encoding="utf-8",
    )
    return str(path)


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("a.png", True), ("a.JPG", True), ("a.jpeg", True), ("a.bmp", True),
        ("a.webp", True), ("a.gif", True), ("a.svg", True), ("a.tiff", True),
        ("a.pdf", False), ("a.txt", False), ("a", False), ("", False),
    ],
)
def test_is_supported(filename, expected):
    assert ImageLoader.is_supported(filename) is expected


# ---------------- SVG ----------------

@pytest.mark.parametrize("width, height", [(400, 400), (401, 400), (402, 403), (37, 41), (803, 199)])
def test_svg_loads_at_any_width(qapp, tmp_path, width, height):
    """
    QImage pads scanlines to 4 bytes, so reshaping to width*3 only worked when
    width*3 was already a multiple of 4. Three widths out of four failed.
    """
    info = ImageLoader.load_image(_write_svg(tmp_path / "shape.svg", width, height))
    assert info.cv_image.shape[2] == 3
    assert info.cv_image.dtype == np.uint8
    assert info.width > 0 and info.height > 0


@pytest.mark.parametrize("width, height", [(800, 200), (200, 800), (500, 500)])
def test_svg_keeps_its_aspect_ratio(qapp, tmp_path, width, height):
    info = ImageLoader.load_image(_write_svg(tmp_path / "shape.svg", width, height))
    assert info.aspect_ratio == pytest.approx(width / height, rel=0.02)


def test_svg_renders_content_on_a_white_background(qapp, tmp_path):
    info = ImageLoader.load_image(_write_svg(tmp_path / "shape.svg", 120, 120))
    assert info.cv_image.min() < 40, "the black rectangle was not rendered"
    assert info.cv_image.max() > 215, "the white background is missing"
    corner = tuple(int(c) for c in info.cv_image[0, 0])
    assert corner == (255, 255, 255)


def test_invalid_svg_reports_an_error(qapp, tmp_path):
    path = tmp_path / "broken.svg"
    path.write_text("<svg this is not valid", encoding="utf-8")
    with pytest.raises(ImageLoadError, match="SVG"):
        ImageLoader.load_image(str(path))


# ---------------- raster ----------------

def test_transparent_png_is_composited_onto_white(qapp, tmp_path):
    path = str(tmp_path / "alpha.png")
    rgba = np.zeros((100, 137, 4), np.uint8)
    rgba[20:80, 20:80] = [0, 0, 0, 255]
    cv2.imwrite(path, rgba)

    info = ImageLoader.load_image(path)
    assert (info.width, info.height) == (137, 100)
    assert tuple(int(c) for c in info.cv_image[0, 0]) == (255, 255, 255)
    assert tuple(int(c) for c in info.cv_image[50, 50]) == (0, 0, 0)


@pytest.mark.parametrize("extension", [".png", ".bmp", ".jpg", ".tiff", ".webp"])
def test_common_raster_formats_load(qapp, tmp_path, extension):
    path = str(tmp_path / f"img{extension}")
    cv2.imwrite(path, np.full((60, 80, 3), 128, np.uint8))

    info = ImageLoader.load_image(path)
    assert (info.width, info.height) == (80, 60)
    assert info.cv_image.shape == (60, 80, 3)


def test_grayscale_png_becomes_three_channels(qapp, tmp_path):
    path = str(tmp_path / "gray.png")
    cv2.imwrite(path, np.full((40, 50), 90, np.uint8))
    assert ImageLoader.load_image(path).cv_image.shape == (40, 50, 3)


def test_animated_gif_uses_the_first_frame(qapp, tmp_path):
    from PIL import Image

    path = str(tmp_path / "anim.gif")
    frames = [
        Image.new("RGB", (40, 30), (0, 0, 0)),
        Image.new("RGB", (40, 30), (255, 255, 255)),
    ]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)

    info = ImageLoader.load_image(path)
    assert (info.width, info.height) == (40, 30)
    assert info.cv_image.mean() < 60, "expected the first (black) frame"


# ---------------- error reporting ----------------

def test_missing_file_reports_an_error(qapp, tmp_path):
    with pytest.raises(ImageLoadError, match="não encontrado"):
        ImageLoader.load_image(str(tmp_path / "ghost.png"))


def test_unsupported_extension_reports_an_error(qapp, tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")
    with pytest.raises(ImageLoadError, match="não suportado"):
        ImageLoader.load_image(str(path))


def test_empty_path_reports_an_error(qapp):
    with pytest.raises(ImageLoadError):
        ImageLoader.load_image("")


def test_corrupt_file_reports_an_error(qapp, tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"definitely not a png")
    with pytest.raises(ImageLoadError):
        ImageLoader.load_image(str(path))


def test_try_load_image_returns_the_message_instead_of_raising(qapp, tmp_path):
    info, error = ImageLoader.try_load_image(str(tmp_path / "ghost.png"))
    assert info is None
    assert error and "não encontrado" in error


def test_try_load_image_returns_info_on_success(qapp, tmp_path):
    path = str(tmp_path / "ok.png")
    cv2.imwrite(path, np.full((20, 20, 3), 200, np.uint8))

    info, error = ImageLoader.try_load_image(path)
    assert error is None
    assert info.filename == "ok.png"
