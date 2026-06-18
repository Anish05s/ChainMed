from pathlib import Path
import qrcode

QR_DIR = Path(__file__).resolve().parent.parent / "static" / "qr"


def ensure_qr_dir() -> None:
    QR_DIR.mkdir(parents=True, exist_ok=True)


def generate_shipment_qr(shipment_id: str, verification_url: str | None = None) -> str:
    """Encode the verification URL (or shipment ID as fallback) into a QR PNG.
    Returns relative URL path to the saved image."""
    ensure_qr_dir()
    # Encode the full URL so mobile scanners open the right page directly.
    content = verification_url if verification_url else shipment_id
    img = qrcode.make(content)
    filename = f"{shipment_id}.png"
    img.save(QR_DIR / filename)
    return f"/static/qr/{filename}"
