"""Windows: DPAPI, Credential Manager, registry autostart, DWM window styling."""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import os
from pathlib import Path

NAME = "windows"
FLYOUT_BORDERLESS = True
APP_DIR = "ClaudeUsageTray"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DPAPI_PREFIX = "dpapi:"
CREDENTIAL_TARGET = "Claude Code-credentials"
ERROR_ALREADY_EXISTS = 183
_mutex = None  # keeps the single-instance mutex alive for the whole process


def data_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / APP_DIR


# ---------------------------------------------------------------- secrets (DPAPI)
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt(data: bytes, protect_it: bool) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    source = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    result = _Blob()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if protect_it else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)):
        raise OSError("DPAPI call failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32 = ctypes.windll.kernel32
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def protect(name: str, value: str) -> str:
    """Encrypts for the current Windows user; `name` is unused here (kept for the shared interface)."""
    if not value:
        return ""
    return DPAPI_PREFIX + base64.b64encode(_crypt(value.encode("utf-8"), True)).decode("ascii")


def unprotect(stored: str) -> str:
    """Decrypts a stored value; plain legacy values are returned unchanged."""
    if stored and stored.startswith(DPAPI_PREFIX):
        try:
            return _crypt(base64.b64decode(stored[len(DPAPI_PREFIX):]), False).decode("utf-8")
        except Exception:
            return ""
    return stored or ""


# ---------------------------------------------------------------- Claude Code credentials
class _Credential(ctypes.Structure):
    _fields_ = [("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32),
                ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_uint32 * 2), ("BlobSize", ctypes.c_uint32),
                ("Blob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p), ("UserName", ctypes.c_wchar_p)]


def native_credentials() -> str:
    """Claude Code's entry in the Windows Credential Manager (JSON text), or ''."""
    try:
        advapi32 = ctypes.windll.advapi32
        advapi32.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.POINTER(_Credential))]
        advapi32.CredFree.argtypes = [ctypes.c_void_p]
        pointer = ctypes.POINTER(_Credential)()
        if not advapi32.CredReadW(CREDENTIAL_TARGET, 1, 0, ctypes.byref(pointer)):  # 1 = generic
            return ""
        try:
            blob = bytes(pointer.contents.Blob[:pointer.contents.BlobSize])
        finally:
            advapi32.CredFree(pointer)
        for encoding in ("utf-8", "utf-16-le"):
            try:
                text = blob.decode(encoding)
            except UnicodeDecodeError:
                continue
            if "claudeAiOauth" in text:
                return text
    except (OSError, AttributeError):
        pass
    return ""


# ---------------------------------------------------------------- autostart
def autostart_enabled() -> bool:
    import winreg
    from .. import APP_NAME
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enable: bool, command: str) -> None:
    import winreg
    from .. import APP_NAME
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- process / session
def acquire_single_instance() -> bool:
    global _mutex
    try:
        from .. import APP_NAME
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}_SingleInstance")
        return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except (OSError, AttributeError):
        return True


def system_language() -> str:
    try:
        return "hu" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x0E else "en"
    except (OSError, AttributeError):
        return "en"


# ---------------------------------------------------------------- appearance
def prefers_dark() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return not winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
    except OSError:
        return False


def style_window(window, dark: bool) -> None:
    """Dark title bar and rounded corners on Windows 10/11 (silently ignored where unsupported)."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        for attribute, value in ((20, int(dark)), (33, 2)):  # immersive dark mode, rounded corners
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(ctypes.c_int(value)), 4)
    except (OSError, AttributeError):
        pass


def work_area(window=None) -> tuple:
    """(left, top, right, bottom) of the screen area not covered by the taskbar."""
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom
