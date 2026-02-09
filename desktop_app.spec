# -*- mode: python ; coding: utf-8 -*-

import os
onnxruntime_dir = os.path.join('venv', 'Lib', 'site-packages', 'onnxruntime', 'capi')

a = Analysis(
    ['desktop_app.py'],
    pathex=[],
    binaries=[
        (os.path.join(onnxruntime_dir, 'onnxruntime.dll'), 'onnxruntime/capi'),
        (os.path.join(onnxruntime_dir, 'onnxruntime_providers_shared.dll'), 'onnxruntime/capi'),
        (os.path.join(onnxruntime_dir, 'onnxruntime_pybind11_state.pyd'), 'onnxruntime/capi'),
    ],
    datas=[('models/silero_vad.onnx', 'models')],
    hiddenimports=[
        'pystray._win32',
        'sounddevice',
        'speech_recognition',
        'soundfile',
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_pybind11_state',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Packages not used by desktop app
        'whisper',
        'ollama',
        'torch',
        'gradio',
        'scipy',
        'pyautogui',
        'matplotlib',
        'pandas',
        'IPython',
        'jupyter',
        'notebook',
        # Test modules
        'pytest',
        'unittest',
        'tkinter.test',
        'numpy.testing',
        # Unused stdlib
        'xmlrpc',
        'pydoc',
        'doctest',
        'lib2to3',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SpeechToText',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'vcruntime140_1.dll',
        'ucrtbase.dll',
        'python3*.dll',
        'onnxruntime*.dll',
        'onnxruntime*.pyd',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
