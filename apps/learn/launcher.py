"""Start/reuse this workspace's learning server without a visible console."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

from server import IDENTITY

HERE = Path(__file__).resolve().parent
RUNTIME = HERE / '.runtime'


def health(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/api/health', timeout=.5) as response:
            return json.load(response)
    except Exception:
        return {}


def main():
    RUNTIME.mkdir(exist_ok=True)
    preferred = 8879
    try:
        previous = json.loads((RUNTIME / 'server.json').read_text(encoding='utf-8'))
        if previous.get('identity') == IDENTITY:
            preferred = int(previous['port'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    ports = list(dict.fromkeys([preferred, *range(8879, 8890)]))
    for port in ports:
        status = health(port)
        if status.get('service') == 'posterpilot-learn' and status.get('identity') == IDENTITY:
            webbrowser.open(f'http://127.0.0.1:{port}')
            print(f'Learning app: http://127.0.0.1:{port}')
            return 0
    for port in ports:
        # A bind conflict makes our process exit; never terminate the other service.
        with (RUNTIME/'stdout.log').open('ab') as out, (RUNTIME/'stderr.log').open('ab') as err:
            process = subprocess.Popen([sys.executable, str(HERE/'server.py'), '--port', str(port)],
                cwd=str(HERE), stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        for _ in range(40):
            if process.poll() is not None:
                break
            status = health(port)
            if status.get('identity') == IDENTITY and status.get('pid') == process.pid:
                webbrowser.open(f'http://127.0.0.1:{port}')
                print(f'Learning app: http://127.0.0.1:{port}')
                return 0
            time.sleep(.1)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
    print('Could not start. Check apps/learn/.runtime/stderr.log. Ports 8879-8889 may be occupied.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
