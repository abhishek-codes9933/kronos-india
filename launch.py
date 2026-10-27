import subprocess
import sys
import webbrowser
from pathlib import Path
import requests

url='http://127.0.0.1:8765'
try:
    r=requests.get(url+'/api/status',timeout=2)
    if r.ok and 'instruments' in r.json():
        webbrowser.open(url)
        raise SystemExit(0)
except (requests.RequestException,ValueError):pass
raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('server.py'))]))
