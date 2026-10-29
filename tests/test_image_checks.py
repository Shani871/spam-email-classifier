import io
import subprocess
from unittest.mock import Mock
import pytest
from PIL import Image
from src.image_checks import extract_image_content


def test_rejects_invalid_and_oversized_uploads():
    with pytest.raises(ValueError):
        extract_image_content(b"not an image")
    with pytest.raises(ValueError, match="10 MB"):
        extract_image_content(b"x" * (10 * 1024 * 1024 + 1))


def test_qr_decodes_without_fetching_destination(monkeypatch):
    cv2 = pytest.importorskip("cv2")
    import src.image_checks as checks
    monkeypatch.setattr(checks.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("ocr", 30)))
    monkeypatch.setattr("requests.get", Mock(side_effect=AssertionError("QR must not fetch destinations")))
    matrix = cv2.QRCodeEncoder_create().encode("https://example.com/test")
    matrix = cv2.copyMakeBorder(matrix, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=255)
    image = Image.fromarray(matrix).resize((480, 480))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    result = extract_image_content(buffer.getvalue())
    assert result["qr_destinations"] == ["https://example.com/test"]
    assert result["warnings"]
