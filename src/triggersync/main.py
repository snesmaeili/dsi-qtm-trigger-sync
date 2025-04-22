"""
CLI for synchronized QTM + parallel triggers.
"""

import argparse
import asyncio
import sys
import pathlib
import os
if __package__:
    from .parallel_client import ParallelClient
    from .qtm_client import QTMClient
else:
    # when run as a standalone script, add this directory to sys.path and import directly
    _current_dir = pathlib.Path(__file__).resolve().parent
    if str(_current_dir) not in sys.path:
        sys.path.insert(0, str(_current_dir))
    from parallel_client import ParallelClient
    from qtm_client import QTMClient
from bids import BIDSLayout
from mne_bids import BIDSPath


def get_next_session(subject: str, root: str) -> str:
    # Ensure BIDS root exists
    try:
        # Attempt to list existing sessions
        layout = BIDSLayout(root, validate=False)
    except ValueError as e:
        print(f"[!] Warning: {e} - creating BIDS root directory {root}")
        os.makedirs(root, exist_ok=True)
        layout = BIDSLayout(root, validate=False)
    ses = sorted({f.entities.get("session") for f in layout.get(subject=subject) if f.entities.get("session")})
    # Return numeric session label (BIDSPath will prefix with 'ses-')
    return f"{len(ses)+1:02d}"


def build_bids_path(subject, task, root):
    # Normalize subject label: strip 'sub-' prefix if present
    subj_id = subject[4:] if subject.lower().startswith("sub-") else subject
    session = get_next_session(subj_id, root)
    # Allow custom .qtm extension (disable BIDSPath validation)
    bp = BIDSPath(subject=subj_id, session=session, task=task,
                  suffix="qtm", extension=".qtm", root=root, check=False)
    # Create parent directories of the target file
    file_path = bp.fpath
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return str(file_path)


async def main(args):
    out = build_bids_path(args.subject, args.task, args.bids_root)
    
    qtm = QTMClient(host=args.host, version=args.version)
    paral = None
    
    try:
        await qtm.connect(password=args.password)
        print(f"[+] Connected to QTM at {args.host}")

        if args.triggers:
            paral = ParallelClient(address=int(args.address, 0), pulse_ms=args.pulse)
            print(f"[+] Initialized parallel port at {args.address}")

        print(f"[+] Starting recording (duration: {args.duration}s)")
        await qtm.start_recording(args.duration)

        if args.triggers:
            await asyncio.gather(
                qtm.conn.set_qtm_event("TaskStart"),
                paral.send(args.start_code)
            )
            print(f"[+] Sent start triggers (QTM event + parallel code {args.start_code})")
        else:
            await qtm.conn.set_qtm_event("TaskStart")
            print("[+] Sent start trigger (QTM event)")

        print(f"[+] Recording in progress. Waiting for {args.duration} seconds...")
        await asyncio.sleep(max(0, args.duration - 0.5))

        if args.triggers:
            await asyncio.gather(
                qtm.conn.set_qtm_event("TaskEnd"),
                paral.send(args.end_code)
            )
            print(f"[+] Sent end triggers (QTM event + parallel code {args.end_code})")
        else:
            await qtm.conn.set_qtm_event("TaskEnd")
            print("[+] Sent end trigger (QTM event)")

        print("[+] Stopping recording and saving file...")
        await qtm.stop_recording(out)
        print(f"[+] Saved session to {out}")
        
    except ConnectionError as e:
        print(f"[!] Connection error: {e}")
        return 1
    except asyncio.TimeoutError:
        print("[!] Operation timed out. Check if QTM is running correctly.")
        return 1
    except Exception as e:
        print(f"[!] Error: {e}")
        return 1
    finally:
        if qtm.conn:
            try:
                await qtm.disconnect()
                print("[+] Disconnected from QTM")
            except Exception as e:
                print(f"[!] Error during disconnection: {e}")
    
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DSI-24 & QTM trigger sync")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--version", default="1.22")
    parser.add_argument("--password", default="")
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--task", default="walking")
    parser.add_argument("--bids_root", required=True)
    parser.add_argument("--triggers", action="store_true")
    parser.add_argument("--address", default="0x4000")
    parser.add_argument("--pulse", type=float, default=5.0)
    parser.add_argument("--start_code", type=int, default=1)
    parser.add_argument("--end_code", type=int, default=2)
    args = parser.parse_args()
    
    try:
        exit_code = asyncio.run(main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user")
        sys.exit(130)