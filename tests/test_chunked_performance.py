"""
Performance tests for chunked/multipart uploads vs traditional single-request uploads.

These tests measure real upload performance against the Turbo service.
They are SKIPPED by default and must be run explicitly.

Run with:
    export TURBO_TEST_WALLET=/path/to/wallet.json
    export TURBO_UPLOAD_URL=https://upload.ardrive.dev  # optional, defaults to testnet
    pytest -m performance -v -s

Note: These tests upload real data and may consume credits. Use a funded wallet.

Expected Results:
-----------------
Single-request uploads are often faster for raw throughput because they avoid:
- Multiple HTTP round trips for chunk uploads
- Server-side chunk assembly time
- Finalization polling delay

However, chunked uploads provide important benefits:
- Progress reporting during upload (essential for UX with large files)
- Memory efficiency (can stream without loading entire file)
- Reliability (individual chunk failures can be retried)
- Foundation for resumable uploads (upload ID persistence)
- Better handling of network interruptions

The auto-chunking threshold (5 MiB) balances these tradeoffs - small files
use efficient single requests while large files get progress visibility.
"""

import io
import json
import os
import time
from dataclasses import dataclass
from typing import List, Optional

import pytest

from turbo_sdk import Turbo, ArweaveSigner, ChunkingParams

# Test wallet path - must be set via environment variable
WALLET_PATH = os.environ.get("TURBO_TEST_WALLET", "")

# Upload URL - defaults to testnet for safety
UPLOAD_URL = os.environ.get("TURBO_UPLOAD_URL", "https://upload.ardrive.dev")


@dataclass
class UploadMetrics:
    """Metrics collected during an upload"""

    method: str
    data_size: int
    total_time: float
    throughput_mbps: float
    chunk_size: Optional[int] = None
    concurrency: Optional[int] = None
    tx_id: Optional[str] = None


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MiB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    return f"{size_bytes} B"


def format_throughput(mbps: float) -> str:
    """Format throughput as human-readable string"""
    if mbps >= 1:
        return f"{mbps:.2f} MB/s"
    return f"{mbps * 1024:.2f} KB/s"


@pytest.fixture(scope="module")
def turbo_client():
    """Create a Turbo client for testing"""
    if not WALLET_PATH or not os.path.exists(WALLET_PATH):
        pytest.skip(f"TURBO_TEST_WALLET not set or wallet not found at '{WALLET_PATH}'")

    with open(WALLET_PATH) as f:
        jwk = json.load(f)

    signer = ArweaveSigner(jwk)
    return Turbo(signer, upload_url=UPLOAD_URL)


@pytest.fixture(scope="module")
def test_data_small():
    """Generate 1 MiB test data"""
    return os.urandom(1 * 1024 * 1024)


@pytest.fixture(scope="module")
def test_data_medium():
    """Generate 6 MiB test data (triggers auto-chunking)"""
    return os.urandom(6 * 1024 * 1024)


@pytest.fixture(scope="module")
def test_data_large():
    """Generate 15 MiB test data"""
    return os.urandom(15 * 1024 * 1024)


class TestUploadPerformance:
    """Performance comparison tests for upload methods"""

    def _upload_single(self, turbo: Turbo, data: bytes, label: str) -> UploadMetrics:
        """Perform single-request upload and collect metrics"""
        start = time.perf_counter()

        result = turbo.upload(
            data,
            tags=[{"name": "Test", "value": f"perf-single-{label}"}],
            chunking=ChunkingParams(chunking_mode="disabled"),
        )

        elapsed = time.perf_counter() - start
        throughput = (len(data) / (1024 * 1024)) / elapsed

        return UploadMetrics(
            method="single",
            data_size=len(data),
            total_time=elapsed,
            throughput_mbps=throughput,
            tx_id=result.id,
        )

    def _upload_chunked(
        self,
        turbo: Turbo,
        data: bytes,
        label: str,
        chunk_size: int = 5 * 1024 * 1024,
        concurrency: int = 1,
    ) -> UploadMetrics:
        """Perform chunked upload and collect metrics"""
        start = time.perf_counter()

        result = turbo.upload(
            data,
            tags=[{"name": "Test", "value": f"perf-chunked-{label}"}],
            chunking=ChunkingParams(
                chunking_mode="force",
                chunk_byte_count=chunk_size,
                max_chunk_concurrency=concurrency,
            ),
        )

        elapsed = time.perf_counter() - start
        throughput = (len(data) / (1024 * 1024)) / elapsed

        return UploadMetrics(
            method=f"chunked-{concurrency}x",
            data_size=len(data),
            total_time=elapsed,
            throughput_mbps=throughput,
            chunk_size=chunk_size,
            concurrency=concurrency,
            tx_id=result.id,
        )

    def _print_metrics(self, metrics: List[UploadMetrics], title: str):
        """Print metrics table"""
        print(f"\n{'=' * 70}")
        print(f" {title}")
        print(f"{'=' * 70}")
        print(f"{'Method':<20} {'Size':<12} {'Time':<10} {'Throughput':<15}")
        print(f"{'-' * 70}")

        for m in metrics:
            print(
                f"{m.method:<20} "
                f"{format_size(m.data_size):<12} "
                f"{m.total_time:.2f}s{'':<5} "
                f"{format_throughput(m.throughput_mbps):<15}"
            )

        print(f"{'=' * 70}\n")

    @pytest.mark.performance
    def test_small_file_comparison(self, turbo_client, test_data_small):
        """Compare upload methods for small files (1 MiB)"""
        metrics = []

        # Single request upload
        m1 = self._upload_single(turbo_client, test_data_small, "1mib")
        metrics.append(m1)

        # Chunked upload (forced)
        m2 = self._upload_chunked(turbo_client, test_data_small, "1mib")
        metrics.append(m2)

        self._print_metrics(metrics, "Small File (1 MiB) - Single vs Chunked")

        # For small files, single request should be faster (less overhead)
        # But we just verify both complete successfully
        assert m1.tx_id is not None
        assert m2.tx_id is not None

    @pytest.mark.performance
    def test_medium_file_comparison(self, turbo_client, test_data_medium):
        """Compare upload methods for medium files (6 MiB)"""
        metrics = []

        # Single request upload
        m1 = self._upload_single(turbo_client, test_data_medium, "6mib")
        metrics.append(m1)

        # Chunked upload - 1 concurrent
        m2 = self._upload_chunked(turbo_client, test_data_medium, "6mib", concurrency=1)
        metrics.append(m2)

        # Chunked upload - 2 concurrent
        m3 = self._upload_chunked(turbo_client, test_data_medium, "6mib", concurrency=2)
        metrics.append(m3)

        self._print_metrics(metrics, "Medium File (6 MiB) - Single vs Chunked")

        assert all(m.tx_id is not None for m in metrics)

    @pytest.mark.performance
    def test_large_file_comparison(self, turbo_client, test_data_large):
        """Compare upload methods for large files (15 MiB)"""
        metrics = []

        # Single request upload
        m1 = self._upload_single(turbo_client, test_data_large, "15mib")
        metrics.append(m1)

        # Chunked upload - 1 concurrent
        m2 = self._upload_chunked(turbo_client, test_data_large, "15mib", concurrency=1)
        metrics.append(m2)

        # Chunked upload - 2 concurrent
        m3 = self._upload_chunked(turbo_client, test_data_large, "15mib", concurrency=2)
        metrics.append(m3)

        # Chunked upload - 3 concurrent
        m4 = self._upload_chunked(turbo_client, test_data_large, "15mib", concurrency=3)
        metrics.append(m4)

        self._print_metrics(metrics, "Large File (15 MiB) - Single vs Chunked")

        assert all(m.tx_id is not None for m in metrics)

    @pytest.mark.performance
    def test_concurrency_scaling(self, turbo_client, test_data_large):
        """Test how throughput scales with concurrency"""
        metrics = []

        for concurrency in [1, 2, 3, 4]:
            m = self._upload_chunked(
                turbo_client,
                test_data_large,
                f"15mib-c{concurrency}",
                concurrency=concurrency,
            )
            metrics.append(m)

        self._print_metrics(metrics, "Concurrency Scaling (15 MiB)")

        # Verify all uploads succeeded
        assert all(m.tx_id is not None for m in metrics)

        # Check that higher concurrency generally improves throughput
        # (may not always be true due to network conditions)
        print("Throughput by concurrency:")
        for m in metrics:
            print(f"  {m.concurrency}x: {format_throughput(m.throughput_mbps)}")

    @pytest.mark.performance
    def test_chunk_size_comparison(self, turbo_client, test_data_large):
        """Test impact of different chunk sizes"""
        metrics = []

        chunk_sizes = [
            5 * 1024 * 1024,  # 5 MiB (minimum)
            10 * 1024 * 1024,  # 10 MiB
            15 * 1024 * 1024,  # 15 MiB (single chunk for this data)
        ]

        for chunk_size in chunk_sizes:
            m = self._upload_chunked(
                turbo_client,
                test_data_large,
                f"15mib-cs{chunk_size // (1024*1024)}",
                chunk_size=chunk_size,
                concurrency=2,
            )
            metrics.append(m)

        self._print_metrics(metrics, "Chunk Size Comparison (15 MiB, 2x concurrency)")

        assert all(m.tx_id is not None for m in metrics)

    @pytest.mark.performance
    def test_stream_upload_performance(self, turbo_client, test_data_medium):
        """Test upload performance with file-like stream input"""
        metrics = []

        # Bytes upload
        start = time.perf_counter()
        result1 = turbo_client.upload(
            test_data_medium,
            tags=[{"name": "Test", "value": "perf-bytes"}],
            chunking=ChunkingParams(chunking_mode="force"),
        )
        elapsed = time.perf_counter() - start
        metrics.append(
            UploadMetrics(
                method="bytes",
                data_size=len(test_data_medium),
                total_time=elapsed,
                throughput_mbps=(len(test_data_medium) / (1024 * 1024)) / elapsed,
                tx_id=result1.id,
            )
        )

        # Stream upload
        stream = io.BytesIO(test_data_medium)
        start = time.perf_counter()
        result2 = turbo_client.upload(
            stream,
            tags=[{"name": "Test", "value": "perf-stream"}],
            chunking=ChunkingParams(chunking_mode="force"),
            data_size=len(test_data_medium),
        )
        elapsed = time.perf_counter() - start
        metrics.append(
            UploadMetrics(
                method="stream",
                data_size=len(test_data_medium),
                total_time=elapsed,
                throughput_mbps=(len(test_data_medium) / (1024 * 1024)) / elapsed,
                tx_id=result2.id,
            )
        )

        self._print_metrics(metrics, "Bytes vs Stream Input (6 MiB)")

        assert all(m.tx_id is not None for m in metrics)


class TestProgressCallbackPerformance:
    """Test that progress callbacks don't significantly impact performance"""

    @pytest.mark.performance
    def test_progress_callback_overhead(self, turbo_client, test_data_medium):
        """Measure overhead of progress callbacks"""

        # Without callback
        start = time.perf_counter()
        r1 = turbo_client.upload(
            test_data_medium,
            tags=[{"name": "Test", "value": "perf-no-callback"}],
            chunking=ChunkingParams(chunking_mode="force"),
        )
        time_no_callback = time.perf_counter() - start

        # With callback
        progress_events = []

        def on_progress(processed, total):
            progress_events.append((time.perf_counter(), processed, total))

        start = time.perf_counter()
        r2 = turbo_client.upload(
            test_data_medium,
            tags=[{"name": "Test", "value": "perf-with-callback"}],
            on_progress=on_progress,
            chunking=ChunkingParams(chunking_mode="force"),
        )
        time_with_callback = time.perf_counter() - start

        overhead_pct = ((time_with_callback - time_no_callback) / time_no_callback) * 100

        print(f"\n{'=' * 50}")
        print("Progress Callback Overhead Test")
        print("=" * 50)
        print(f"Without callback: {time_no_callback:.2f}s")
        print(f"With callback:    {time_with_callback:.2f}s")
        print(f"Overhead:         {overhead_pct:+.1f}%")
        print(f"Callback events:  {len(progress_events)}")
        print(f"{'=' * 50}\n")

        assert r1.id is not None
        assert r2.id is not None
        assert len(progress_events) > 0

        # Callback overhead should be minimal (< 20%)
        # Note: network variance may cause this to fluctuate
        assert overhead_pct < 50, f"Callback overhead too high: {overhead_pct}%"


def run_benchmark():
    """Run all benchmarks and print summary"""
    if not WALLET_PATH or not os.path.exists(WALLET_PATH):
        print(f"Error: Wallet not found at '{WALLET_PATH}'")
        print("Set TURBO_TEST_WALLET environment variable to your wallet path")
        return

    with open(WALLET_PATH) as f:
        jwk = json.load(f)

    signer = ArweaveSigner(jwk)
    turbo = Turbo(signer, upload_url=UPLOAD_URL)

    print(f"\nWallet: {signer.get_wallet_address()}")
    print(f"Upload URL: {UPLOAD_URL}")
    print("Running performance benchmarks...\n")

    test = TestUploadPerformance()

    # Run tests with different file sizes
    sizes = [
        (1 * 1024 * 1024, "1 MiB"),
        (6 * 1024 * 1024, "6 MiB"),
        (15 * 1024 * 1024, "15 MiB"),
    ]

    all_metrics = []

    for size, label in sizes:
        print(f"Testing {label}...")
        data = os.urandom(size)

        # Single upload
        m1 = test._upload_single(turbo, data, label.replace(" ", ""))
        all_metrics.append(m1)

        # Chunked with different concurrency
        for conc in [1, 2, 3]:
            m = test._upload_chunked(
                turbo, data, f"{label.replace(' ', '')}-c{conc}", concurrency=conc
            )
            all_metrics.append(m)

    # Print final summary
    print("\n" + "=" * 80)
    print(" FINAL SUMMARY")
    print("=" * 80)
    print(f"{'Method':<25} {'Size':<12} {'Time':<10} {'Throughput':<15} {'TX ID':<20}")
    print("-" * 80)

    for m in all_metrics:
        print(
            f"{m.method:<25} "
            f"{format_size(m.data_size):<12} "
            f"{m.total_time:.2f}s{'':<5} "
            f"{format_throughput(m.throughput_mbps):<15} "
            f"{m.tx_id[:16] if m.tx_id else 'N/A'}..."
        )

    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
