# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

# Project root (one level up from build_scripts/)
ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

# Collect ALL onnxruntime files (this is what makes it work in frozen context)
ort_datas, ort_binaries, ort_hiddenimports = collect_all('onnxruntime')

a = Analysis(
    [os.path.join(ROOT, 'src', 'desktop_app.py')],
    pathex=[ROOT],
    binaries=ort_binaries,
    datas=[(os.path.join(ROOT, 'models', 'silero_vad.onnx'), 'models')] + ort_datas,
    hiddenimports=[
        'pystray._win32',
        'sounddevice',
        'speech_recognition',
        'soundfile',
    ] + ort_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(SPECPATH, 'pyi_rth_onnxruntime.py')],
    excludes=[
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
        'pytest',
        'unittest',
        'tkinter.test',
        'numpy.testing',
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
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
