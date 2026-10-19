"""Run regression tests in a temporary checkout without operator config or data.

Usage: python backend/run_isolated_tests.py [pytest arguments]
Requires the existing backend requirements in the selected Python environment.
"""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile


def main():
    repository = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix='paper-format-regression-') as directory:
        root = Path(directory)
        for name in ['app', 'tests']:
            shutil.copytree(repository / 'backend' / name, root / 'backend' / name,
                            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc'))
        shutil.copytree(repository / 'samples', root / 'samples')
        for name in ['README.md', 'EVALUATION.md']:
            if (repository / name).is_file():
                shutil.copy2(repository / name, root / name)
        environment = os.environ.copy()
        for key in list(environment):
            if key.endswith('_DB_PATH'):
                environment.pop(key)
        environment.update(PYTHONPATH=str(root / 'backend'), WORKFLOW_DB_PATH='',
                           SUBMISSION_FILE_DIR=str(root / 'backend' / 'data' / 'submissions'),
                           COOKIE_SECURE='true', GOOGLE_OAUTH_CLIENT_ID='',
                           SECRET_KEY=secrets.token_urlsafe(48))
        print('Running in a temporary checkout; local .env and application databases are excluded.', flush=True)
        arguments = sys.argv[1:] or ['backend/tests', '-q']
        return subprocess.run([sys.executable, '-m', 'pytest', *arguments], cwd=root, env=environment).returncode


if __name__ == '__main__':
    raise SystemExit(main())
