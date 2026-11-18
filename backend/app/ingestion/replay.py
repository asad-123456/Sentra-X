"""Feed a JSONL file through the real ingestion path.
Usage (from backend/): python -m app.ingestion.replay tests/fixtures/replay/ac1_100.jsonl [--rate 5]"""
from __future__ import annotations

import argparse
import time
from dataclasses import asdict, fields

from app.database import SyncSessionLocal
from app.ingestion.service import IngestSummary, ingest_raws
from app.ingestion.sources import ReplaySource


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--rate", type=float, default=0, help="alerts per second (0 = as fast as possible)")
    args = ap.parse_args(argv)

    raws = ReplaySource(args.file).fetch()
    factory = SyncSessionLocal
    total = IngestSummary()

    def add(part: IngestSummary) -> None:
        for f in fields(total):
            setattr(total, f.name, getattr(total, f.name) + getattr(part, f.name))

    if args.rate > 0:
        chunk = max(1, round(args.rate))
        for i in range(0, len(raws), chunk):
            add(ingest_raws(factory, raws[i:i + chunk]))
            time.sleep(chunk / args.rate)
    else:
        add(ingest_raws(factory, raws))

    for k, v in asdict(total).items():
        print(f"{k:20} {v}")


if __name__ == "__main__":
    main()
