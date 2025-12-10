#!/usr/bin/env python3
"""Backup Stremio data files to a GitHub repo.

This script copies the three Stremio data files to a given GitHub repository
under a specified folder (default: `BKP_Stremio/<timestamp>/`) and pushes a
commit. It is intended to be run from a cron or systemd timer every 15 minutes.

Security: Do NOT hardcode your token. Provide it via the `GITHUB_TOKEN` env var
or the `--token` argument. The token pasted into chat should be revoked — do
not include it in files.
"""
import argparse
import datetime
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import json
from pathlib import Path
from datetime import datetime as dt, timezone


LOG = logging.getLogger('stremio-bkp')

# Simple XOR key for token encoding (not cryptographically secure, just obfuscation)
TOKEN_XOR_KEY = 0x7F

# Embedded encoded GitHub token (encode with encode_token.py script)
# Leave empty to disable, or set to an XOR-encoded token string
EMBEDDED_GITHUB_TOKEN = " J'<;5'\n                       5F+L1O2'F>K,"


def xor_encode(data: str, key: int = TOKEN_XOR_KEY) -> str:
    """Encode string using XOR (simple obfuscation, not secure)."""
    return ''.join(chr(ord(c) ^ key) for c in data)


def xor_decode(data: str, key: int = TOKEN_XOR_KEY) -> str:
    """Decode XOR-encoded string."""
    return ''.join(chr(ord(c) ^ key) for c in data)


def run(cmd, cwd=None, capture=False, check=True):
    LOG.debug('RUN: %s', ' '.join(cmd))
    res = subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)
    if check and res.returncode != 0:
        LOG.error('Command failed: %s\nstdout: %s\nstderr: %s', cmd, res.stdout, res.stderr)
        raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)
    return res


def mask_token(token: str) -> str:
    if not token:
        return ''
    if len(token) <= 6:
        return '***'
    return token[:3] + '...' + token[-3:]


def backup_and_push(token, repo, branch, remote_dir, files, work_dir=None):
    if not token:
        raise RuntimeError('No GITHUB token provided. Set GITHUB_TOKEN env or use --token.')

    repo = repo.rstrip('/')
    # Use timezone-aware UTC datetime (for logging only)
    timestamp = dt.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    
    # Resolve work_dir to absolute path if provided
    if work_dir:
        work_dir = str(Path(work_dir).resolve())

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        clone_dir = td_path / 'repo'

        clone_url = f'https://{token}@github.com/{repo}.git'
        LOG.info('Cloning remote repo %s (masked token=%s)', repo, mask_token(token))
        run(['git', 'clone', '--depth', '1', '--branch', branch, clone_url, str(clone_dir)])

        # Use fixed target folder (no timestamp subfolders)
        target_path = clone_dir / remote_dir
        target_path.mkdir(parents=True, exist_ok=True)

        # Copy files
        for src in files:
            if work_dir:
                # Resolve relative to work_dir
                src_path = Path(work_dir) / src
            else:
                # Resolve as absolute path
                src_path = Path(src).resolve()
            if not src_path.exists():
                LOG.warning('Source file missing, skipping: %s', src_path)
                continue
            shutil.copy2(src_path, target_path / src_path.name)
            LOG.info('Copied %s -> %s', src_path, target_path)

        # Git add/commit/push
        run(['git', 'add', '.'], cwd=str(clone_dir))
        commit_msg = f'Backup update: {timestamp}'
        try:
            run(['git', 'commit', '-m', commit_msg], cwd=str(clone_dir))
        except subprocess.CalledProcessError:
            LOG.info('Nothing to commit (files unchanged)')
            return False

        LOG.info('Setting authenticated remote and pushing to %s (branch: %s)', repo, branch)
        # Ensure origin uses the token so push is authenticated even if git strips creds
        run(['git', 'remote', 'set-url', 'origin', clone_url], cwd=str(clone_dir))
        try:
            res = run(['git', 'push', 'origin', branch], cwd=str(clone_dir), capture=True, check=False)
            if res.returncode != 0:
                LOG.error('Git push failed. stdout:\n%s\nstderr:\n%s', res.stdout, res.stderr)
                raise subprocess.CalledProcessError(res.returncode, ['git', 'push', 'origin', branch], output=res.stdout, stderr=res.stderr)
        except subprocess.CalledProcessError:
            LOG.error('Push failed. Common causes: token missing push rights, branch protection, or wrong repo. Ensure token has "repo" (or "public_repo") scope and user can push to %s/%s', repo, branch)
            raise

    return True


def main():
    parser = argparse.ArgumentParser(description='Backup Stremio data files to GitHub')
    parser.add_argument('--token', help='GitHub personal access token (or set GITHUB_TOKEN)')
    parser.add_argument('--token-file', default='~/.stremio_bkp_token', help='Path to a file that stores the GitHub token (mode 600)')
    parser.add_argument('--save-token', action='store_true', help='Save provided --token into --token-file with mode 600')
    parser.add_argument('--repo', required=True, help='GitHub repo in form owner/repo')
    parser.add_argument('--branch', default='main', help='Branch to push to')
    parser.add_argument('--remote-dir', default='BKP_Stremio', help='Folder in repo to store backups')
    parser.add_argument('--work-dir', default='.', help='Working directory where Stremio folder lives')
    parser.add_argument('--files', nargs='+', default=['Stremio/data/movies.json', 'Stremio/data/series.json', 'Stremio/data/catalogs.json'], help='Files to back up')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format='[%(levelname)s] %(message)s')

    # Resolve token: explicit arg > env var > embedded token > token file
    token = args.token or os.environ.get('GITHUB_TOKEN')
    
    # If no token from arg/env, try embedded token
    if not token and EMBEDDED_GITHUB_TOKEN.strip():
        try:
            token = xor_decode(EMBEDDED_GITHUB_TOKEN)
            LOG.info('Using embedded GitHub token')
        except Exception as e:
            LOG.warning('Could not decode embedded token: %s', e)

    token_file_path = Path(args.token_file).expanduser()

    def write_token_file(p: Path, tkn: str):
        p.parent.mkdir(parents=True, exist_ok=True)
        # Encode token using XOR before writing
        encoded = xor_encode(tkn.strip())
        with open(p, 'w') as f:
            f.write(encoded)
        try:
            os.chmod(p, 0o600)
        except Exception:
            LOG.warning('Could not set permissions on token file: %s', p)
        LOG.info('Token saved to %s (encoded)', p)

    def read_token_file(p: Path):
        try:
            if p.exists():
                encoded = p.read_text().strip()
                # Decode XOR-encoded token
                return xor_decode(encoded)
        except Exception as e:
            LOG.warning('Could not read token file %s: %s', p, e)
        return None

    # If user requested saving the token into the token file, do it now
    if args.save_token:
        if not args.token:
            LOG.error('--save-token requires --token to be provided')
            sys.exit(2)
        write_token_file(token_file_path, args.token)
        LOG.info('Saved token to %s (permissions 600 if supported)', token_file_path)

    # Try token file if token still not provided
    if not token:
        token = read_token_file(token_file_path)

    if not token:
        LOG.error('No GitHub token provided. Set GITHUB_TOKEN environment variable, pass --token, or create a token file at %s', token_file_path)
        sys.exit(2)

    try:
        ok = backup_and_push(token, args.repo, args.branch, args.remote_dir, args.files, work_dir=args.work_dir)
        if ok:
            LOG.info('Backup completed and pushed successfully')
            sys.exit(0)
        else:
            LOG.info('No changes to push')
            sys.exit(0)
    except Exception as e:
        LOG.exception('Backup failed: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
