"""YunZeHui 云泽汇优化 — PyInstaller 入口."""
import sys

sys.path.insert(0, __file__.rsplit('\\', 1)[0])

from YunZeHui.__main__ import main

if __name__ == '__main__':
    sys.exit(main())
