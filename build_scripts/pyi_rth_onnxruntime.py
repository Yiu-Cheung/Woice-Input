"""Runtime hook to pre-load onnxruntime DLL dependencies before import."""
import os
import sys

if sys.platform == "win32" and getattr(sys, 'frozen', False):
    import ctypes

    base = sys._MEIPASS
    ort_capi = os.path.join(base, "onnxruntime", "capi")

    os.add_dll_directory(base)
    if os.path.isdir(ort_capi):
        os.add_dll_directory(ort_capi)

    k32 = ctypes.windll.kernel32
    k32.LoadLibraryExW.restype = ctypes.c_void_p
    k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]

    # Pre-load system DLLs that onnxruntime.dll depends on.
    # All 5 are needed when sounddevice's PortAudio DLLs are also bundled.
    system32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    for dep in ['dxgi.dll', 'dbghelp.dll', 'SETUPAPI.dll', 'MSVCP140.dll', 'MSVCP140_1.dll']:
        k32.LoadLibraryExW(os.path.join(system32, dep), None, 0)

    # Pre-load onnxruntime DLLs
    for dll in ['onnxruntime.dll', 'onnxruntime_providers_shared.dll']:
        for search_dir in [ort_capi, base]:
            path = os.path.join(search_dir, dll)
            if os.path.isfile(path):
                k32.LoadLibraryExW(path, None, 0x00000008)
                break
