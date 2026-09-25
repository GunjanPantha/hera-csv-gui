"""Entry point for the portable Windows package."""
from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parent
os.environ['TCL_LIBRARY'] = str(root / 'tcl' / 'tcl8.6')
os.environ['TK_LIBRARY'] = str(root / 'tcl' / 'tk8.6')

try:
    import hera_csv
    hera_csv.main()
except Exception:
    import ctypes
    import tempfile
    import traceback
    folder = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir())) / 'HERA_CSV'
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / 'error.log'
    log.write_text(traceback.format_exc(), encoding='utf-8')
    ctypes.windll.user32.MessageBoxW(None, f'HERA CSV could not start.\n\nDetails: {log}', 'HERA CSV', 0x10)
    sys.exit(1)
