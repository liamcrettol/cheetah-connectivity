"""Read-only status helper, safe to run while the worker runs."""
import json
from pathlib import Path
import sys
HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path: sys.path.insert(0,HERE)
from start_vcf_v2_balanced_overnight import OUT, process_running

def main():
    latest = OUT/'latest_launch.json'
    if not latest.exists():
        print('No background launch recorded yet.'); return
    launch = json.loads(latest.read_text())
    print('PID:',launch['pid'],'process present:',process_running(launch['pid']))
    status = OUT/'STATUS.json'
    print(status.read_text() if status.exists() else 'Starting/importing ArcPy; status not written yet.')
    log = Path(launch['log'])
    if log.exists():
        print('\nRecent log:')
        print('\n'.join(log.read_text(errors='replace').splitlines()[-18:]))
    print('\nFinal/partial summary:',OUT/'SUMMARY.md')

if __name__ == '__main__':
    main()
