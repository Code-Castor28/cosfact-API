"""
Genera un certificado .p12 autofirmado para tests de firma XML.
Uso: python scripts/generate_test_cert.py
"""
import os
import sys
from pathlib import Path

# Asegurar que el proyecto está en sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.development")

from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import django
django.setup()

from django.conf import settings


def main():
    fixtures_dir = BASE_DIR / "tests" / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generar clave RSA 2048
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 2. Crear certificado X.509 autofirmado
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Test DGII Cert"),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(private_key, hashes.SHA256())
    )

    # 3. Empaquetar como PKCS12 con PIN conocido
    pin = b"test1234"
    p12_data = serialization.pkcs12.serialize_key_and_certificates(
        name=b"test_cert",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(pin),
    )

    p12_path = fixtures_dir / "test_cert.p12"
    with open(p12_path, "wb") as f:
        f.write(p12_data)
    print(f"[OK] .p12 guardado en {p12_path}")

    # 4. Cifrar el PIN con Fernet
    fernet_key = getattr(settings, "FERNET_KEY", None) or os.environ.get("FERNET_KEY")
    if not fernet_key:
        print("[ERROR] FERNET_KEY no configurada en settings/environ")
        sys.exit(1)

    f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
    pin_cifrado = f.encrypt(pin).decode()

    pin_path = fixtures_dir / "test_pin.txt"
    with open(pin_path, "w") as f:
        f.write(pin_cifrado)
    print(f"[OK] PIN cifrado guardado en {pin_path}")

    # 5. Verificación
    descifrado = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
    pin_desc = descifrado.decrypt(pin_cifrado.encode()).decode()
    assert pin_desc == "test1234", "PIN no coincide"
    print("[OK] Verificación: PIN descifrado correctamente")

    # 6. Mostrar serial del certificado para tests
    print(f"[INFO] Serial del certificado: {cert.serial_number}")


if __name__ == "__main__":
    main()
