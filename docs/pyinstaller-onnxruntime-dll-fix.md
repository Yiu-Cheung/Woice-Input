# PyInstaller + onnxruntime DLL Loading Fix

## Problem

When building a PyInstaller onefile exe that bundles both **onnxruntime** and **sounddevice**, `onnxruntime.dll` fails to initialize at runtime with Windows error 1114 (`ERROR_DLL_INIT_FAILED`):

```
ImportError: DLL load failed while importing onnxruntime_pybind11_state:
A dynamic link library (DLL) initialization routine failed.
```

The exe works fine when only onnxruntime is bundled. It also works fine when onnxruntime + PIL are bundled. But the moment sounddevice (and its PortAudio DLLs) enter the bundle, onnxruntime breaks.

## Environment

- Python 3.14.2, Windows 10 (10.0.19045)
- onnxruntime 1.24.1
- PyInstaller 6.18.0
- sounddevice 0.5.1 (bundles `libportaudio64bit.dll`, `libportaudio64bit-asio.dll`)

## Root Cause

### Background: DLL search order in frozen Python

PyInstaller's onefile mode extracts everything to a temp directory (`sys._MEIPASS`). Python 3.8+ changed DLL search behavior — `os.add_dll_directory()` is now required to add custom search paths. But the core issue here isn't about *finding* DLLs — it's about loading the *wrong version* of system DLLs.

### The actual conflict

`onnxruntime.dll` depends on several system DLLs:
- `dxgi.dll` (DirectX)
- `dbghelp.dll` (Debug Help Library)
- `SETUPAPI.dll` (Setup API)
- `MSVCP140.dll` (MSVC++ Runtime)
- `MSVCP140_1.dll` (MSVC++ Runtime)

When sounddevice's `libportaudio64bit.dll` is in the same bundle, it shares some of these dependencies (notably `SETUPAPI.dll`, `MSVCP140.dll`). On the build machine, **non-System32 versions** of these DLLs were present on `PATH`:

| DLL | Loaded from (wrong) | Should be from |
|-----|---------------------|----------------|
| `dbghelp.dll` | `C:\Program Files\Oculus\Support\oculus-runtime\` | `C:\Windows\System32\` |
| `msvcp140.dll` | `C:\Program Files\BellSoft\LibericaJDK-24\bin\` | `C:\Windows\System32\` |

Inside `_MEIPASS`, the Windows loader picks up whichever version it finds first. When the wrong version of a dependency loads first (e.g., an older `SETUPAPI.dll` or mismatched `MSVCP140.dll`), `onnxruntime.dll`'s `DllMain()` returns FALSE, causing error 1114.

### Why sounddevice triggers it

Without sounddevice, the DLL search order happens to find the right versions. When sounddevice's PortAudio DLLs are added to the bundle, they bring in additional DLL dependencies that alter the search/load order, causing the wrong versions to be picked up first.

## Bisection Process

This was identified through systematic binary bisection:

| Test build | Contents | Result |
|-----------|----------|--------|
| `test_ort.exe` | onnxruntime only | PASS |
| `test_bisect.exe` | onnxruntime + PIL | FAIL |
| `test_pil_collect.exe` | `--collect-all onnxruntime` + `--collect-all PIL` | PASS |
| `test_pil_hidden.exe` | `--collect-all onnxruntime` + `--hidden-import PIL` | PASS |
| `test_sd.exe` (2 DLLs) | onnxruntime + sounddevice, preload dxgi+dbghelp | FAIL |
| `test_sd.exe` (5 DLLs) | onnxruntime + sounddevice, preload all 5 system DLLs | **PASS** |

Comparing the PKG TOC between working (163 entries) and failing (180 entries) builds revealed 7 extra DLLs in the failing build, including `libportaudio64bit.dll` and `libportaudio64bit-asio.dll`.

The `pefile` module was used to enumerate `onnxruntime.dll`'s import table to identify all system DLL dependencies.

## Solution

Pre-load all 5 system DLLs **from System32** using `LoadLibraryExW` before onnxruntime is imported. This ensures the correct system versions are loaded before any bundled DLLs can interfere.

### Implementation

The fix is applied in two places for defense-in-depth:

#### 1. Runtime hook (`pyi_rth_onnxruntime.py`)

Runs before any Python code in the frozen exe:

```python
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

    # Pre-load system DLLs from System32 (all 5 needed when sounddevice is bundled)
    system32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    for dep in ['dxgi.dll', 'dbghelp.dll', 'SETUPAPI.dll', 'MSVCP140.dll', 'MSVCP140_1.dll']:
        k32.LoadLibraryExW(os.path.join(system32, dep), None, 0)

    # Pre-load onnxruntime DLLs with LOAD_WITH_ALTERED_SEARCH_PATH (0x00000008)
    for dll in ['onnxruntime.dll', 'onnxruntime_providers_shared.dll']:
        for search_dir in [ort_capi, base]:
            path = os.path.join(search_dir, dll)
            if os.path.isfile(path):
                k32.LoadLibraryExW(path, None, 0x00000008)
                break
```

#### 2. Top of `desktop_app.py`

Same logic at the very top of the main script, before any imports:

```python
import sys
import os
if sys.platform == "win32" and getattr(sys, 'frozen', False):
    import ctypes
    _k32 = ctypes.windll.kernel32
    _k32.LoadLibraryExW.restype = ctypes.c_void_p
    _k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    _sys32 = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32')
    _base = sys._MEIPASS
    for _dep in ['dxgi.dll', 'dbghelp.dll', 'SETUPAPI.dll', 'MSVCP140.dll', 'MSVCP140_1.dll']:
        _k32.LoadLibraryExW(os.path.join(_sys32, _dep), None, 0)
    os.add_dll_directory(_base)
    _ort_capi = os.path.join(_base, "onnxruntime", "capi")
    if os.path.isdir(_ort_capi):
        os.add_dll_directory(_ort_capi)
    for _dll in ['onnxruntime.dll', 'onnxruntime_providers_shared.dll']:
        for _d in [_ort_capi, _base]:
            _p = os.path.join(_d, _dll)
            if os.path.isfile(_p):
                _k32.LoadLibraryExW(_p, None, 0x00000008)
                break
```

### PyInstaller spec (`desktop_app.spec`)

Uses `collect_all('onnxruntime')` to bundle all onnxruntime files, and references the runtime hook:

```python
from PyInstaller.utils.hooks import collect_all
ort_datas, ort_binaries, ort_hiddenimports = collect_all('onnxruntime')

a = Analysis(
    ['desktop_app.py'],
    binaries=ort_binaries,
    datas=[('models/silero_vad.onnx', 'models')] + ort_datas,
    hiddenimports=[...] + ort_hiddenimports,
    runtime_hooks=['pyi_rth_onnxruntime.py'],
    excludes=['whisper', 'ollama', 'torch', 'scipy', ...],
)
```

Build command:
```
venv\Scripts\pyinstaller.exe desktop_app.spec --clean
```

**Important**: Do NOT build with `pyinstaller --onefile desktop_app.py` — this ignores the spec file and generates a minimal config that won't include the runtime hook or onnxruntime binaries.

## Key Technical Details

### `LoadLibraryExW` flags

- Flag `0` (default): Load from System32 using standard search order. Used for system DLLs.
- Flag `0x00000008` (`LOAD_WITH_ALTERED_SEARCH_PATH`): Resolves the DLL's own dependencies relative to its location. Used for `onnxruntime.dll` and `onnxruntime_providers_shared.dll` so they find each other in `_MEIPASS\onnxruntime\capi\`.

### Why `os.add_dll_directory()` alone isn't enough

`os.add_dll_directory()` affects Python's `ctypes` and extension module loading, but it doesn't control Windows' native DLL loader order. When `onnxruntime.dll` is loaded by the PE loader, it follows Windows' own DLL search order, which may find bundled (wrong) versions of system DLLs before the correct System32 ones. By explicitly loading the System32 versions first with `LoadLibraryExW`, they're already in memory when onnxruntime needs them.

### Why `ctypes.WinDLL()` doesn't work

`ctypes.WinDLL(path)` uses `LoadLibrary` without the `LOAD_WITH_ALTERED_SEARCH_PATH` flag, so onnxruntime.dll can't find its sibling `onnxruntime_providers_shared.dll`.

## Approaches That Did NOT Work

1. **`os.add_dll_directory()` only** — insufficient; doesn't control native loader order
2. **`ctypes.WinDLL(path)`** — no `LOAD_WITH_ALTERED_SEARCH_PATH` flag
3. **Pre-loading only dxgi.dll + dbghelp.dll** — works without sounddevice, fails with it
4. **PyInstaller `--add-binary` for onnxruntime DLLs** — same search order problem
5. **Onedir mode** — same DLL conflict occurs

## Lessons Learned

1. **Error 1114 means DllMain returned FALSE** — the DLL was *found* but failed to initialize. This is different from "DLL not found" errors.
2. **Binary bisection is essential** — isolate which bundled package causes the conflict by building test exes with different combinations.
3. **Use `pefile` to enumerate imports** — `pip install pefile` then inspect the DLL's import table to find all dependencies.
4. **Third-party software pollutes DLL search paths** — Oculus, JDK, and other software install DLLs to directories on PATH that can shadow System32 versions.
5. **Always build with the spec file** — `pyinstaller desktop_app.spec`, never `pyinstaller desktop_app.py`.
