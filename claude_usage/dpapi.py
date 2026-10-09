"""Windows DPAPI helpers: secrets are bound to the current Windows user."""
from __future__ import annotations

import base64
import ctypes

PREFIX = "dpapi:"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(data: bytes, protect: bool) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    source = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    result = _Blob()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise OSError("DPAPI call failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def encrypt(text: str) -> str:
    if not text:
        return ""
    return PREFIX + base64.b64encode(_crypt(text.encode("utf-8"), True)).decode("ascii")


def decrypt(text: str) -> str:
    """Decrypts a stored value; plain legacy values are returned unchanged."""
    if text and text.startswith(PREFIX):
        try:
            return _crypt(base64.b64decode(text[len(PREFIX):]), False).decode("utf-8")
        except Exception:
            return ""
    return text or ""
