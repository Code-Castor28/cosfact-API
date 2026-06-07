from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings
from django.core.files.base import ContentFile

from empresas.models import CertificadoDigital, Empresa

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def p12_pin() -> bytes:
    return b"test1234"


@pytest.fixture
def p12_pin_encrypted() -> str:
    pin_txt = FIXTURES_DIR / "test_pin.txt"
    return pin_txt.read_text().strip()


@pytest.fixture
def fernet_key() -> bytes:
    key = getattr(settings, "FERNET_KEY", None)
    if key is None:
        key = "9Thw-W58npEtdZ_SPCsEt-ySN8hS9-r7KhbRmICC144="
    return key.encode() if isinstance(key, str) else key


@pytest.fixture
def p12_bytes() -> bytes:
    p12_path = FIXTURES_DIR / "test_cert.p12"
    return p12_path.read_bytes()


@pytest.fixture
def private_key(p12_bytes, p12_pin):
    key, _cert, _cas = pkcs12.load_key_and_certificates(p12_bytes, p12_pin)
    return key


@pytest.fixture
def certificate(p12_bytes, p12_pin):
    _key, cert, _cas = pkcs12.load_key_and_certificates(p12_bytes, p12_pin)
    return cert


@pytest.fixture
def empresa(db):
    return Empresa.objects.create(
        rnc="99999999999",
        razon_social="Test Empresa DGII",
        ambiente=Empresa.AMBIENTE_TEST,
        estado=Empresa.ESTADO_ACTIVA,
    )


@pytest.fixture
def certificado_digital(empresa, p12_bytes, p12_pin, fernet_key):
    f = Fernet(fernet_key)
    pin_cifrado = f.encrypt(p12_pin).decode()

    cert = CertificadoDigital.objects.create(
        empresa=empresa,
        alias="Test Cert",
        pin_cifrado=pin_cifrado,
        vigencia_desde="2025-01-01",
        vigencia_hasta="2026-12-31",
        activo=True,
    )
    cert.archivo.save("test_cert.p12", ContentFile(p12_bytes))
    return cert
