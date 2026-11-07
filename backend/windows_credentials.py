"""Private Windows credential ACLs; no shell commands or optional packages."""
import ctypes
from ctypes import wintypes as w
from functools import lru_cache
import os


@lru_cache(maxsize=1)
def _api():
    if os.name != 'nt':
        raise OSError('Windows security APIs are unavailable')
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    ptr = ctypes.c_void_p
    signatures = {
        'OpenProcessToken': ([w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL),
        'GetTokenInformation': ([w.HANDLE, ctypes.c_int, ptr, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL),
        'ConvertSidToStringSidW': ([ptr, ctypes.POINTER(ptr)], w.BOOL),
        'ConvertStringSecurityDescriptorToSecurityDescriptorW': ([w.LPCWSTR, w.DWORD, ctypes.POINTER(ptr), ctypes.POINTER(w.DWORD)], w.BOOL),
        'GetSecurityDescriptorDacl': ([ptr, ctypes.POINTER(w.BOOL), ctypes.POINTER(ptr), ctypes.POINTER(w.BOOL)], w.BOOL),
        'SetNamedSecurityInfoW': ([w.LPWSTR, ctypes.c_int, w.DWORD, ptr, ptr, ptr, ptr], w.DWORD),
        'GetNamedSecurityInfoW': ([w.LPCWSTR, ctypes.c_int, w.DWORD, ptr, ptr, ptr, ptr, ctypes.POINTER(ptr)], w.DWORD),
        'ConvertSecurityDescriptorToStringSecurityDescriptorW': ([ptr, w.DWORD, w.DWORD, ctypes.POINTER(ptr), ctypes.POINTER(w.DWORD)], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        function = getattr(adv, name)
        function.argtypes, function.restype = args, result
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    kernel.LocalFree.argtypes = [ptr]
    kernel.LocalFree.restype = ptr
    return adv, kernel


@lru_cache(maxsize=1)
def current_user_sid():
    adv, kernel = _api()
    token = w.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        size = w.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buffer, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        # TOKEN_USER begins with SID_AND_ATTRIBUTES, whose first field is PSID.
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p)).contents
        text = ctypes.c_void_p()
        if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.wstring_at(text)
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.CloseHandle(token)


def set_dacl(path, sddl):
    """Replace, rather than append to, the object's discretionary ACL."""
    adv, kernel = _api()
    descriptor = ctypes.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        present, defaulted, dacl = w.BOOL(), w.BOOL(), ctypes.c_void_p()
        if not adv.GetSecurityDescriptorDacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not present.value or not dacl.value:
            raise ValueError('An explicit non-null credential ACL is required')
        error = adv.SetNamedSecurityInfoW(str(path), 1, 4 | 0x80000000, None, None, dacl, None)
        if error:
            raise ctypes.WinError(error)
    finally:
        kernel.LocalFree(descriptor)


def secure_path(path, *, directory=False):
    if path.lstat().st_file_attributes & 0x400:
        raise ValueError('Credential paths must not be reparse points')
    inherit = 'OICI' if directory else ''
    set_dacl(path, f'D:P(A;{inherit};FA;;;{current_user_sid()})(A;{inherit};FA;;;SY)')


def security_descriptor(path):
    """Read DACL metadata for native regression checks; never reads credentials."""
    adv, kernel = _api()
    descriptor, text = ctypes.c_void_p(), ctypes.c_void_p()
    error = adv.GetNamedSecurityInfoW(str(path), 1, 4, None, None, None, None, ctypes.byref(descriptor))
    if error:
        raise ctypes.WinError(error)
    try:
        if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 4, ctypes.byref(text), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.wstring_at(text)
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.LocalFree(descriptor)
