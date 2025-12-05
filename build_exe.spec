# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('templates', 'templates'),
    ('模板.xlsx', '.'),
    ('bilibili_subtitle_downloader.py', '.'),
    ('download_and_summarize.py', '.'),
    ('llm_client.py', '.'),
    ('subtitle_summarizer.py', '.'),
    ('process_video_info.py', '.'),
    ('app.py', '.'),
]
binaries = []
hiddenimports = [
    'flask',
    'requests',
    'werkzeug',
    'jinja2',
    'click',
    'itsdangerous',
    'markupsafe',
    'openpyxl',
    'openpyxl.styles',
    'openpyxl.cell',
    'openpyxl.workbook',
    'video_transcriber',  # Ensure this is found
]

# Collect packages that might have binary dependencies or data
for package in ['faster_whisper', 'ctranslate2', 'nvidia-cublas-cu12', 'nvidia-cudnn-cu12']:
    try:
        tmp_bin, tmp_data, tmp_hidden = collect_all(package)
        binaries += tmp_bin
        datas += tmp_data
        hiddenimports += tmp_hidden
    except Exception as e:
        print(f"Warning: Failed to collect {package}: {e}")

block_cipher = None

a = Analysis(
    ['start_web.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

import sys

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BilibiliSubtitleSummarizer.exe' if sys.platform == 'win32' else 'BilibiliSubtitleSummarizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

