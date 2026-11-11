"""YunZeHui 打包脚本：onedir 免安装版。

用法：python build_exe.py
输出：dist/YunZeHui/YunZeHui.exe
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
WORK = os.path.join(ROOT, 'build')

from PyInstaller.__main__ import run as pyi_run

opts = [
    '--name=YunZeHui',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--onedir',
    f'--distpath={DIST}',
    f'--workpath={WORK}',
    f'--specpath={ROOT}',
    f'--paths={os.path.join(ROOT, "YunZeHui")}',
    '--hidden-import=psutil',
    '--hidden-import=psutil._pswindows',
    '--hidden-import=psutil._common',
    '--collect-submodules=psutil',
    '--collect-submodules=YunZeHui',
    '--exclude-module=PySide6.QtWebEngineCore',
    '--exclude-module=PySide6.QtWebEngineWidgets',
    '--exclude-module=PySide6.QtQml',
    '--exclude-module=PySide6.QtQuick',
    '--exclude-module=PySide6.Qt3D',
    '--exclude-module=tkinter',
    '--exclude-module=matplotlib',
    '--exclude-module=numpy',
    '--exclude-module=PyQt5',
    '--exclude-module=PyQt6',
    os.path.join(ROOT, 'YunZeHui', 'launch.py'),
]
pyi_run(opts)
print('BUILD OK ->', os.path.join(DIST, 'YunZeHui'))
