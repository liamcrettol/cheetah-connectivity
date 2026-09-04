"""Start one hidden standalone ArcGIS Python worker; no PowerShell required."""
import ctypes
from ctypes import wintypes
import datetime as dt
import json
from pathlib import Path
import subprocess

OUT = Path(r'C:\cheetah\diagnostics\vcf_v2_balanced_overnight_v1')
PYTHON = Path(r'C:\Users\lcrettol\AppData\Local\Programs\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe')
WORKER = Path(__file__).resolve().with_name('run_vcf_v2_balanced_overnight.py')

def process_running(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        if ctypes.get_last_error() == 87:
            return False
        return True  # Uncertainty/access denied: never launch a duplicate.
    try:
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259
    finally:
        kernel.CloseHandle(handle)

def main():
    if not PYTHON.is_file() or not WORKER.is_file():
        raise FileNotFoundError('ArcGIS Python or worker script missing')
    OUT.mkdir(parents=True, exist_ok=True)
    latest = OUT/'latest_launch.json'
    if latest.exists():
        previous = json.loads(latest.read_text())
        if process_running(previous['pid']):
            print('Worker already running (or PID cannot be ruled out):', previous['pid'])
            print('Log:',previous['log'])
            return
    lock = OUT/'RUNNING.lock'
    if lock.exists():
        pid = int(lock.read_text().strip())
        if process_running(pid):
            print('Existing worker or inaccessible PID:',pid)
            return
        # Remove only this diagnostic's lock after confirming its PID exited.
        lock.unlink()
        print('Removed stale diagnostic lock for exited PID',pid,'; checkpoints preserved.')
    logfile = OUT/('console_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.log')
    with logfile.open('x', encoding='utf-8') as handle:
        process = subprocess.Popen([str(PYTHON),'-u',str(WORKER)], cwd=str(WORKER.parent),
             stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
             creationflags=subprocess.CREATE_NO_WINDOW)
    latest.write_text(json.dumps({'pid':process.pid,'log':str(logfile),'worker':str(WORKER)},indent=2),encoding='utf-8')
    print('Started background diagnostic. PID:',process.pid)
    print('Log:',logfile)
    print('Status:',OUT/'STATUS.json')
    print('It must pass input preflight before starting any solver.')
    print('Keep this computer powered on and plugged in; do not restart or sign out.')
    print('No production data or ArcGIS map will be changed.')

if __name__ == '__main__':
    main()
