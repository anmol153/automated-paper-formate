"""Run the real-API frontend harness against a disposable backend and database."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0, help='Local test port; 0 selects a free port')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix='paper-format-ui-') as directory, socket.socket() as listener:
        # Reserve the listener ourselves and pass it to Uvicorn. Never probe an
        # unrelated server that happened to occupy the requested port.
        listener.bind(('127.0.0.1', args.port))
        listener.listen(128)
        port = listener.getsockname()[1]
        root = Path(directory)
        shutil.copytree(repository / 'backend' / 'app', root / 'backend' / 'app',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        environment = os.environ.copy()
        for key in list(environment):
            if key.endswith('_DB_PATH'):
                environment.pop(key)
        environment.update(PYTHONPATH=str(root / 'backend'), WORKFLOW_DB_PATH=str(root / 'workflow.db'),
                           SUBMISSION_FILE_DIR=str(root / 'files'), COOKIE_SECURE='false',
                           GOOGLE_OAUTH_CLIENT_ID='', SECRET_KEY=secrets.token_urlsafe(48),
                           API_BASE=f'http://127.0.0.1:{port}/api/v1')
        subprocess.run([sys.executable, '-c', 'import os; from pathlib import Path; from app.storage.database import initialize_if_empty; initialize_if_empty(Path(os.environ["WORKFLOW_DB_PATH"]))'], cwd=root, env=environment, check=True)
        with (root / 'backend.log').open('w') as log:
            backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--fd', str(listener.fileno())], pass_fds=(listener.fileno(),), cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                for attempt in range(100):
                    if backend.poll() is not None:
                        raise RuntimeError('Disposable backend exited; choose another port if it is already occupied')
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=1) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError('Disposable backend did not become ready')
                print('Frontend checks use a disposable backend; local configuration/data are excluded.', flush=True)
                return subprocess.run(['node', 'component-test.mjs'], cwd=repository / 'frontend', env=environment).returncode
            finally:
                backend.terminate()
                try:
                    backend.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    backend.kill()
                    backend.wait()


if __name__ == '__main__':
    raise SystemExit(main())
