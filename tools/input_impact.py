"""Measure archived-directory selection and mocked bar-fetch impact; never network.

python tools/input_impact.py --output docs/input-truthfulness/measurements.json
Requires the milestone base in local Git history. Timings are fixture timings,
not forecasts for Alpaca; SDK batches exclude hidden pagination and retries.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import socket
import statistics
import subprocess
import sys
import time
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import market_data, pipeline, universe  # noqa: E402
from tests.fakes import FakeAlpaca, FakeDataClient  # noqa: E402
from tests.synthetic import make_ohlcv  # noqa: E402
from datetime import date, datetime, timezone  # noqa: E402

BASE = '7e6d056672079e2ac46b6e5a84ae9589f1648e80'


def git_file(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{BASE}:{path}'])


def baseline_module():
    mod = types.ModuleType('baseline_universe')
    mod.__file__ = str(ROOT / 'src/universe.py')
    sys.modules[mod.__name__] = mod
    exec(compile(git_file('src/universe.py'), mod.__file__, 'exec'), mod.__dict__)
    return mod


def measure(module, rows, seeds):
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        stocks, _, _, counts = module.admit(rows, seeds)
        timings.append(time.perf_counter() - start)
    intended = stocks + ([] if 'SPY' in stocks else ['SPY'])
    fake = FakeAlpaca()
    frame = make_ohlcv('flat', days=260, seed=20260910)
    for symbol in intended:
        fake.add_history(symbol, frame)
    start = time.perf_counter()
    frames, stats, _ = pipeline.fetch_universe(FakeDataClient(fake), intended, date(2026, 9, 10),
        market_data.DEFAULT_FEED, pipeline.RunReport(), now=datetime(2026, 9, 10, 22, 30, tzinfo=timezone.utc))
    seconds = time.perf_counter() - start
    assert stats.requested == len(intended) == stats.with_bars and not stats.unfetched
    return {'stocks': len(stocks), 'intended_with_benchmark': len(intended), 'selection_identity': module.identity(stocks),
            'counts': counts, 'estimated_initial_sdk_batches': sum(math.ceil(len(intended[i:i+pipeline.FETCH_CHUNK]) /
                market_data.DEFAULT_BATCH_SIZE) for i in range(0, len(intended), pipeline.FETCH_CHUNK)),
            'mock_sdk_requests': len(fake.bar_requests), 'mock_returned_bars': sum(len(df) for df in frames.values()),
            'selection_median_ms': round(statistics.median(timings) * 1000, 3), 'mock_fetch_seconds': round(seconds, 3)}


def size(raw):
    return {'raw': len(raw), 'gzip': len(gzip.compress(raw, mtime=0))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    cache_raw = git_file('docs/universe-directory.json.gz')
    cache = json.loads(gzip.decompress(cache_raw))
    def blocked(*a, **k):
        raise RuntimeError('network forbidden in input-impact measurement')
    with patch.object(socket.socket, 'connect', blocked), patch.object(socket, 'create_connection', blocked):
        before = measure(baseline_module(), cache['rows'], universe.read_seed())
        after = measure(universe, cache['rows'], universe.read_seed())
    fixture = 'tests/fixtures/page/full.json'
    result = {'base': BASE, 'directory_fetched_at': cache['fetched_at'],
              'directory_compressed_sha256': hashlib.sha256(cache_raw).hexdigest(),
              'before': before, 'after': after, 'full_record_before': size(git_file(fixture)),
              'full_record_after': size((ROOT / fixture).read_bytes()),
              'provider_calls': 0, 'model_calls': 0,
              'limits': ['One archived directory; not point-in-time membership.',
                         'Uniform synthetic 260-bar frames; returned bars and elapsed times are mocked, not live provider measurements.',
                         'Initial SDK batch estimates exclude pagination and retries; no dollar cost is inferred.',
                         '900-second fetch budget and 12-read model cap unchanged; candidate-dependent calls can vary within the cap.']}
    body = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body)
    print(body)


if __name__ == '__main__':
    main()
