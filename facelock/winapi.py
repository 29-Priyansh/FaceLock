"""Thin ctypes wrappers over the Win32 APIs FaceLock needs. No pywin32 dependency."""
import ctypes
import logging
import threading
from ctypes import wintypes

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.CreateWindowExW.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.RegisterPowerSettingNotification.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
user32.UnregisterPowerSettingNotification.argtypes = [wintypes.HANDLE]
user32.GetForegroundWindow.restype = wintypes.HWND
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.LocalFree.argtypes = [ctypes.c_void_p]
wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
wtsapi32.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
wtsapi32.WTSQuerySessionInformationW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_int,
                                                 ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)]
wtsapi32.WTSFreeMemory.argtypes = [ctypes.c_void_p]


# --- Locking -----------------------------------------------------------------

def lock_workstation():
    """Same as Win+L. Returns True if the lock request was accepted."""
    ok = bool(user32.LockWorkStation())
    if not ok:
        log.error("LockWorkStation failed: %s", ctypes.get_last_error())
    return ok


def is_session_locked():
    """True/False from WTSSessionInfoEx; None if the query fails."""
    WTS_CURRENT_SESSION = 0xFFFFFFFF
    WTSSessionInfoEx = 25
    buf = ctypes.c_void_p()
    size = wintypes.DWORD()
    if not wtsapi32.WTSQuerySessionInformationW(None, WTS_CURRENT_SESSION, WTSSessionInfoEx,
                                                ctypes.byref(buf), ctypes.byref(size)):
        return None
    try:
        # WTSINFOEXW: DWORD Level; union (8-byte aligned, it holds LARGE_INTEGERs) of
        # WTSINFOEX_LEVEL1_W {ULONG SessionId @8; SessionState @12; LONG SessionFlags @16; ...}
        flags = ctypes.c_long.from_address(buf.value + 16).value
    finally:
        wtsapi32.WTSFreeMemory(buf)
    if flags == 0:      # WTS_SESSIONSTATE_LOCK
        return True
    if flags == 1:      # WTS_SESSIONSTATE_UNLOCK
        return False
    return None


# --- Process stats (diagnostics) ---------------------------------------------

class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]


def working_set_mb():
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return counters.WorkingSetSize / 2 ** 20


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
    except (AttributeError, OSError):
        pass


# --- Single instance ---------------------------------------------------------

_mutex = None


def acquire_single_instance(name="Local\\FaceLock.SingleInstance"):
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, name)
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


# --- DPAPI -------------------------------------------------------------------

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
                                     ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.POINTER(DATA_BLOB),
                                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
CRYPTPROTECT_UI_FORBIDDEN = 0x1


def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _take(blob):
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))


def dpapi_protect(data: bytes, entropy: bytes) -> bytes:
    src, _keep1 = _blob(data)
    ent, _keep2 = _blob(entropy)
    out = DATA_BLOB()
    if not crypt32.CryptProtectData(ctypes.byref(src), "FaceLock profile", ctypes.byref(ent),
                                    None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    return _take(out)


def dpapi_unprotect(data: bytes, entropy: bytes) -> bytes:
    src, _keep1 = _blob(data)
    ent, _keep2 = _blob(entropy)
    out = DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(src), None, ctypes.byref(ent),
                                      None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
    return _take(out)


# --- Non-activating topmost windows (countdown overlay) ----------------------

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x2, 0x10, 0x40


def toplevel_hwnd(tk_widget):
    return user32.GetAncestor(tk_widget.winfo_id(), 2)  # GA_ROOT


def make_no_activate(hwnd):
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)


def show_no_activate(hwnd):
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
    user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)


def hide_window(hwnd):
    user32.ShowWindow(hwnd, SW_HIDE)


def foreground_window():
    return user32.GetForegroundWindow()


# --- Session / power event listener ------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


GUID_CONSOLE_DISPLAY_STATE = GUID(0x6FE69556, 0x704A, 0x47A0,
                                  (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47))


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016
WM_POWERBROADCAST = 0x0218
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
PBT_APMSUSPEND = 0x4
PBT_APMRESUMESUSPEND = 0x7
PBT_APMRESUMEAUTOMATIC = 0x12
PBT_POWERSETTINGCHANGE = 0x8013


class SessionEvents(threading.Thread):
    """Hidden top-level window that turns Win32 notifications into callback(event) calls.

    Events: lock, unlock, display_off, display_on, suspend, resume, endsession.
    A top-level (not message-only) window is required to receive broadcast messages
    such as WM_POWERBROADCAST and WM_ENDSESSION.
    """

    def __init__(self, callback):
        super().__init__(name="SessionEvents", daemon=True)
        self.callback = callback
        self.hwnd = None
        self._ready = threading.Event()

    def _emit(self, event):
        try:
            self.callback(event)
        except Exception:
            log.exception("session event callback failed")

    def _proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_WTSSESSION_CHANGE:
                if wparam == WTS_SESSION_LOCK:
                    self._emit("lock")
                elif wparam == WTS_SESSION_UNLOCK:
                    self._emit("unlock")
            elif msg == WM_POWERBROADCAST:
                if wparam == PBT_APMSUSPEND:
                    self._emit("suspend")
                elif wparam in (PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC):
                    self._emit("resume")
                elif wparam == PBT_POWERSETTINGCHANGE and lparam:
                    # POWERBROADCAST_SETTING: GUID(16) DataLength(4) Data[...]
                    state = ctypes.c_uint32.from_address(lparam + 20).value
                    self._emit("display_off" if state == 0 else "display_on")  # 2 = dimmed counts as on
                return 1
            elif msg == WM_QUERYENDSESSION:
                return 1
            elif msg == WM_ENDSESSION:
                if wparam:
                    self._emit("endsession")
                return 0
            elif msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception:
            log.exception("wndproc error")
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def run(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(self._proc)  # keep a reference for the lifetime of the window
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "FaceLockSessionEvents"
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "FaceLockSessionEvents", 0,
                                           0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            log.error("event window creation failed: %s", ctypes.get_last_error())
            self._ready.set()
            return
        if not wtsapi32.WTSRegisterSessionNotification(self.hwnd, 0):  # NOTIFY_FOR_THIS_SESSION
            log.error("WTSRegisterSessionNotification failed: %s", ctypes.get_last_error())
        hpower = user32.RegisterPowerSettingNotification(self.hwnd, ctypes.byref(GUID_CONSOLE_DISPLAY_STATE), 0)
        self._ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        wtsapi32.WTSUnRegisterSessionNotification(self.hwnd)
        if hpower:
            user32.UnregisterPowerSettingNotification(hpower)

    def start(self):
        super().start()
        self._ready.wait(5)

    def stop(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
