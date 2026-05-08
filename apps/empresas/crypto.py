# ─── CRYPTO.PY — apps/empresas/crypto.py ───
"""
apps/empresas/crypto.py
Cifrado simétrico Fernet para tokens DGII y datos sensibles.
REQUERIMIENTO: Variable de entorno FERNET_KEY en el servidor.
Generar una vez con:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Y guardarla en /etc/environment o en el .env del VPS (nunca en el repo).
"""
import os
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _get_fernet() -> Fernet:
    key = getattr(settings, "FERNET_KEY", None) or os.environ.get("FERNET_KEY")
    if not key:
        raise EnvironmentError(
            "FERNET_KEY no está configurada. "
            "Genera una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def cifrar(texto: str) -> str:
    """Cifra un string y retorna el texto cifrado como string base64."""
    f = _get_fernet()
    return f.encrypt(texto.encode()).decode()


def descifrar(texto_cifrado: str) -> str:
    """Descifra un string cifrado con Fernet. Lanza InvalidToken si fue manipulado."""
    f = _get_fernet()
    try:
        return f.decrypt(texto_cifrado.encode()).decode()
    except InvalidToken:
        raise ValueError("El token cifrado fue manipulado o la clave es incorrecta.")
