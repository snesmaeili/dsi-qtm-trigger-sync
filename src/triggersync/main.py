"""
CLI for synchronized QTM + parallel triggers.
"""

import argparse
import asyncio
from bids import BIDSLayout
from mne_bids import BIDSPath
from triggersync.parallel_client import ParallelClient
from triggersync.qtm_client import QTMClient


def get_next_session(subject: str, root: str) -> str:
    layout = BIDSLayout(root, validate=False)
    ses = sorted({f.entities.get("session") for f in layout.get(subject=subject) if f.entities.get("session")})
    return f"ses-{len(ses)+1:02d}" if ses else "ses-01"


def build_bids_path(subject, task, root):
    session = get_next_session(subject, root)
    bp = BIDSPath(subject=subject, session=session, task=task,
                  suffix="qtm", extension=".qtm", root=root)
    bp.mkdir(parents=True, exist_ok=True)
    return str(bp.fpath)


async def main(args):
    out = build_bids_path(args.subject, args.task, args.bids_root)

    qtm = QTMClient(host=args.host, version=args.version)
    await qtm.connect(password=args.password)

    if args.triggers:
        paral = ParallelClient(address=int(args.address, 0), pulse_ms=args.pulse)

    await qtm.start_recording(args.duration)

    if args.triggers:
        await asyncio.gather(
            qtm.conn.set_qtm_event("TaskStart"),
            paral.send(args.start_code)
        )
    else:
        await qtm.conn.set_qtm_event("TaskStart")

    await asyncio.sleep(max(0, args.duration - 0.5))

    if args.triggers:
        await asyncio.gather(
            qtm.conn.set_qtm_event("TaskEnd"),
            paral.send(args.end_code)
        )
    else:
        await qtm.conn.set_qtm_event("TaskEnd")

    await qtm.stop_recording(out)
    await qtm.disconnect()
    print(f"[+] Saved session to {out}")


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
    asyncio.run(main(args))