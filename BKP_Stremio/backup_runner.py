#!/usr/bin/env python3
"""Background daemon that downloads Stremio once, then backs up every 15 minutes."""
import sys
import time
import logging
import subprocess
import os
from pathlib import Path
from datetime import datetime as dt, timezone

LOG = logging.getLogger('stremio-backup-runner')
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/tmp/stremio_backup_runner.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Config
BACKUP_SCRIPT = Path(__file__).parent / 'backup_to_github.py'
BACKUP_INTERVAL = 15 * 60  # 15 minutes in seconds
REPO = 'Gujjugaming2k/site_scrap_mv'
BRANCH = 'main'
REMOTE_DIR = 'BKP_Stremio'
WORK_DIR = '/tmp/Stremio'  # Where Stremio is deployed
ZIP_URL = f'https://github.com/{REPO}/raw/{BRANCH}/Stremio.zip'
ZIP_FILE = '/tmp/Stremio.zip'
STATE_FILE = '/tmp/stremio_initialized'  # Track if we've already downloaded


def download_stremio():
    """Download Stremio.zip once."""
    LOG.info('Downloading Stremio.zip from %s...', ZIP_URL)
    try:
        result = subprocess.run(
            ['curl', '-L', ZIP_URL, '-o', ZIP_FILE],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            LOG.error('Failed to download Stremio.zip: %s', result.stderr)
            return False
        
        LOG.info('Downloaded Stremio.zip to %s', ZIP_FILE)
        
        # Extract ZIP
        LOG.info('Extracting ZIP to %s...', WORK_DIR)
        os.makedirs(WORK_DIR, exist_ok=True)
        result = subprocess.run(
            ['unzip', '-o', ZIP_FILE, '-d', WORK_DIR],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            LOG.error('Failed to extract ZIP: %s', result.stderr)
            return False
        
        LOG.info('Stremio extracted successfully')
        return True
    except subprocess.TimeoutExpired:
        LOG.error('Download/extract timed out')
        return False
    except Exception as e:
        LOG.exception('Error downloading Stremio: %s', e)
        return False


def fetch_latest_backup():
    """Fetch the latest backup files from GitHub BKP_Stremio folder."""
    LOG.info('Fetching latest backup from GitHub (%s)...', REMOTE_DIR)
    try:
        # Raw GitHub URLs for the three data files
        backup_files = {
            'movies.json': f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{REMOTE_DIR}/movies.json',
            'series.json': f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{REMOTE_DIR}/series.json',
            'catalogs.json': f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/{REMOTE_DIR}/catalogs.json'
        }
        
        data_dir = Path(WORK_DIR) / 'Stremio' / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        for filename, url in backup_files.items():
            filepath = data_dir / filename
            LOG.info('Downloading %s from %s...', filename, url)
            
            result = subprocess.run(
                ['curl', '-sS', '-L', url, '-o', str(filepath)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and filepath.exists():
                size = filepath.stat().st_size
                if size > 0:
                    LOG.info('Downloaded %s (%d bytes)', filename, size)
                else:
                    LOG.warning('Downloaded %s but file is empty', filename)
            else:
                LOG.warning('Failed to download %s from GitHub', filename)
        
        LOG.info('Latest backup files downloaded to %s', data_dir)
        return True
    except Exception as e:
        LOG.exception('Error fetching latest backup: %s', e)
        return False


def run_backup():
    """Run the backup script once."""
    LOG.info('Starting backup...')
    try:
        cmd = [
            sys.executable,
            str(BACKUP_SCRIPT),
            '--repo', REPO,
            '--branch', BRANCH,
            '--remote-dir', REMOTE_DIR,
            '--work-dir', WORK_DIR
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            LOG.info('Backup completed successfully')
        else:
            LOG.error('Backup failed with return code %d', result.returncode)
            if result.stdout:
                LOG.error('stdout: %s', result.stdout)
            if result.stderr:
                LOG.error('stderr: %s', result.stderr)
    except subprocess.TimeoutExpired:
        LOG.error('Backup timed out after 300 seconds')
    except Exception as e:
        LOG.exception('Error running backup: %s', e)


def main():
    LOG.info('=== Stremio Backup Runner Started ===')
    LOG.info('Backup interval: %d minutes', BACKUP_INTERVAL // 60)
    LOG.info('Repository: %s', REPO)
    LOG.info('Work directory: %s', WORK_DIR)
    LOG.info('Backup script: %s', BACKUP_SCRIPT)
    
    if not BACKUP_SCRIPT.exists():
        LOG.error('Backup script not found: %s', BACKUP_SCRIPT)
        sys.exit(1)
    
    # Check if already initialized
    if not Path(STATE_FILE).exists():
        LOG.info('First run detected - downloading Stremio...')
        if not download_stremio():
            LOG.error('Failed to download Stremio, exiting')
            sys.exit(1)
        
        LOG.info('Stremio extracted successfully')
        
        # Download latest backup files after extraction
        LOG.info('Checking for latest backups to restore...')
        if fetch_latest_backup():
            LOG.info('Latest backup files restored')
        else:
            LOG.warning('Could not restore latest backup (may not exist yet)')
        
        # Mark as initialized
        Path(STATE_FILE).touch()
        LOG.info('Marked as initialized')
    else:
        LOG.info('Stremio already downloaded, skipping download step')
    
    # Fetch latest backup info (on each run for updates)
    LOG.info('Checking for latest backups...')
    fetch_latest_backup()
    
    # Run first backup immediately
    LOG.info('Running initial backup...')
    run_backup()
    
    # Then run every 15 minutes
    try:
        while True:
            LOG.info('Waiting %d seconds until next backup...', BACKUP_INTERVAL)
            time.sleep(BACKUP_INTERVAL)
            run_backup()
    except KeyboardInterrupt:
        LOG.info('Backup runner stopped by user')
        sys.exit(0)
    except Exception as e:
        LOG.exception('Unexpected error in backup runner: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
