"""Supervise only the dedicated shell connector or its named tunnel."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path('/state/shell-app')
SCRIPT = '/workspace/stable-shell-service.py'

def matches_owned_process(command, role):
    return SCRIPT.encode() in command.split(b'\0') and role.encode() in command.split(b'\0')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['shell', 'tunnel'])
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    pidfile = ROOT / ('stable-' + args.role + '.pid')
    if args.stop:
        if not pidfile.exists():
            return
        pid = int(pidfile.read_text())
        try:
            command = Path('/proc/' + str(pid) + '/cmdline').read_bytes()
        except FileNotFoundError:
            return
        if not matches_owned_process(command, args.role):
            raise RuntimeError('PID no longer belongs to the dedicated service; unchanged')
        os.kill(pid, signal.SIGTERM)
        return
    with (ROOT / ('stable-' + args.role + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pidfile.write_text(str(os.getpid()))
        pidfile.chmod(0o600)
        try:
            if args.role == 'shell':
                sys.path.insert(0, '/opt/adapter')
                sys.path.insert(0, '/state/shell-app-deps')
                sys.path.insert(0, '/state/shell-app-code')
                import uvicorn
                from networks.integrations.accounts.controller_service import ControllerAccountsRuntime
                from remote_execution.shell_app import ShellAuthorization, create_app
                from remote_execution.shell_exec import accounts_shell
                runtime = ControllerAccountsRuntime(json.loads(Path('/state/accounts.json').read_text()))
                try:
                    shell = accounts_shell(runtime, os.environ['COGNILODE_EXECUTOR_REF'], ROOT)
                    shell.backend(shell.default)
                    authorization = ShellAuthorization(ROOT, os.environ['SHELL_APP_ORIGIN'])
                    server = create_app(shell, authorization, port=int(os.environ['SHELL_APP_PORT']))
                    uvicorn.run(server.streamable_http_app(), host='0.0.0.0',
                                port=int(os.environ['SHELL_APP_PORT']), access_log=False)
                finally:
                    runtime.close()
            else:
                child = subprocess.Popen([
                    '/state/modified-codex/cloudflared-shell-app', 'tunnel',
                    '--no-autoupdate', '--protocol', 'http2', 'run',
                    '--token-file', '/state/shell-app/stable-tunnel.token'])
                signal.signal(signal.SIGTERM, lambda *_: child.terminate())
                signal.signal(signal.SIGINT, lambda *_: child.terminate())
                code = child.wait()
                if code:
                    raise SystemExit(code)
        finally:
            pidfile.unlink(missing_ok=True)

if __name__ == '__main__':
    main()

