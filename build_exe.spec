# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['start_web.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('模板.xlsx', '.'),
        ('bilibili_subtitle_downloader.py', '.'),
        ('download_and_summarize.py', '.'),
        ('llm_client.py', '.'),
        ('subtitle_summarizer.py', '.'),
        ('process_video_info.py', '.'),
        ('app.py', '.'),
    ],
    hiddenimports=[
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
    ],
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

