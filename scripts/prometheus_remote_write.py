#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import time
import threading
from collections import defaultdict
from typing import Dict, Tuple, Optional, List

import requests
import snappy
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from google.protobuf import descriptor_pool, descriptor_pb2, message_factory


# ---------------------------------------------------------------------------
# Minimal protobuf schema for Prometheus remote_write
# ---------------------------------------------------------------------------

_SCHEMA = None


def _get_msg_class(pool, fq_name: str):
    """
    Get protobuf message class from descriptor pool.

    This function tries multiple APIs to avoid deprecation warnings:
    1) pool.GetMessageClass(fq_name) - newest API (protobuf 4.x+)
    2) message_factory.GetMessageClass(descriptor) - modern API (protobuf 3.x+)
    3) MessageFactory(pool).GetPrototype(descriptor) - legacy API (protobuf 2.x)

    Args:
        pool: DescriptorPool instance
        fq_name: Fully qualified message name (e.g., "prom.Label")

    Returns:
        Python class for the protobuf message
    """
    # Try pool.GetMessageClass (protobuf 4.x+)
    get_cls = getattr(pool, "GetMessageClass", None)
    if callable(get_cls):
        return get_cls(fq_name)

    # Get descriptor for fallback methods
    desc = pool.FindMessageTypeByName(fq_name)

    # Try message_factory.GetMessageClass (protobuf 3.x+)
    get_fn = getattr(message_factory, "GetMessageClass", None)
    if callable(get_fn):
        return get_fn(desc)

    # Fallback for protobuf 2.x; may emit warnings on newer versions
    factory = message_factory.MessageFactory(pool)
    return factory.GetPrototype(desc)


def _init_schema():
    """
    Initialize protobuf schema for Prometheus remote_write protocol.

    This creates a minimal schema dynamically without requiring .proto files.
    The schema matches the official Prometheus remote_write specification:
    https://github.com/prometheus/prometheus/blob/main/prompb/remote.proto

    Protobuf field encoding:
    - number=N: Field number (1-indexed), used for wire format encoding
                Receivers rely on these numbers to decode fields correctly
    - type=N: Field type
        1 = TYPE_DOUBLE (float64)
        3 = TYPE_INT64
        9 = TYPE_STRING
       11 = TYPE_MESSAGE (nested message)
    - label=3: LABEL_REPEATED, indicates a repeated field (list/array)

    These values are from the protobuf specification and MUST remain
    consistent for compatibility with Prometheus and other remote_write receivers.

    Returns:
        Tuple of (Label, Sample, TimeSeries, WriteRequest) message classes
    """

    global _SCHEMA
    if _SCHEMA is not None:
        return _SCHEMA

    # Create file descriptor for our schema
    fdp = descriptor_pb2.FileDescriptorProto()
    fdp.name = "remote_write_minimal.proto"
    fdp.package = "prom"

    # message Label { string name = 1; string value = 2; }
    # Represents a single label name-value pair
    msg = fdp.message_type.add()
    msg.name = "Label"
    msg.field.add(name="name", number=1, type=9)   # TYPE_STRING
    msg.field.add(name="value", number=2, type=9)  # TYPE_STRING

    # message Sample { double value = 1; int64 timestamp = 2; }
    # Represents a single metric observation at a point in time
    msg = fdp.message_type.add()
    msg.name = "Sample"
    msg.field.add(name="value", number=1, type=1)      # TYPE_DOUBLE
    msg.field.add(name="timestamp", number=2, type=3)  # TYPE_INT64 (ms since epoch)

    # message TimeSeries { repeated Label labels = 1; repeated Sample samples = 2; }
    # Represents a metric with its labels and time-series samples
    msg = fdp.message_type.add()
    msg.name = "TimeSeries"
    msg.field.add(name="labels", number=1, label=3, type=11, type_name=".prom.Label")   # LABEL_REPEATED
    msg.field.add(name="samples", number=2, label=3, type=11, type_name=".prom.Sample") # LABEL_REPEATED

    # message WriteRequest { repeated TimeSeries timeseries = 1; }
    # Top-level message containing multiple time series
    msg = fdp.message_type.add()
    msg.name = "WriteRequest"
    msg.field.add(
        name="timeseries", number=1, label=3, type=11, type_name=".prom.TimeSeries"  # LABEL_REPEATED
    )

    # Build descriptor pool and generate message classes
    pool = descriptor_pool.DescriptorPool()
    pool.Add(fdp)

    Label = _get_msg_class(pool, "prom.Label")
    Sample = _get_msg_class(pool, "prom.Sample")
    TimeSeries = _get_msg_class(pool, "prom.TimeSeries")
    WriteRequest = _get_msg_class(pool, "prom.WriteRequest")

    _SCHEMA = (Label, Sample, TimeSeries, WriteRequest)
    return _SCHEMA


# ---------------------------------------------------------------------------
# Remote Write Client
# ---------------------------------------------------------------------------


class RemoteWriteClient:
    """
    A client for sending metrics to Prometheus-compatible remote_write endpoints.

    This client supports:
    - Gauges: arbitrary values that can increase or decrease
    - Counters: monotonically increasing values
    - Histograms: bucketed observations with sum and count

    The client handles:
    - Protobuf serialization according to Prometheus remote_write spec
    - Snappy compression
    - HTTP retries for transient failures
    - Counter state tracking (monotonic increments)
    - Histogram bucketing and cumulative distribution
    """

    def __init__(
        self,
        endpoint: str,
        headers: Optional[Dict] = None,
        timeout: float = 5.0,
        debug: bool = False,
    ):
        """
        Initialize the RemoteWriteClient.

        Args:
            endpoint: The remote_write URL (e.g., https://prometheus/api/v1/write)
            headers: Optional additional HTTP headers (e.g., auth tokens)
            timeout: Request timeout in seconds
            debug: If True, print metrics in Prometheus format before sending
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.debug = debug

        # Initialize protobuf message classes
        self._Label, self._Sample, self._TimeSeries, self._WriteRequest = _init_schema()

        # HTTP session with retry logic for resilience
        sess = requests.Session()
        retry = Retry(total=2, backoff_factor=0.2, status_forcelist=(502, 503, 504))
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=10)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        self._sess = sess

        # Required headers per Prometheus remote_write spec
        self.headers = {
            "Content-Type": "application/x-protobuf",
            "Content-Encoding": "snappy",
            "X-Prometheus-Remote-Write-Version": "0.1.0",
        }
        if headers:
            self.headers.update(headers)

        # State management for stateful metric types
        self._counter_cache: Dict[Tuple[str, frozenset], float] = {}  # Track counter values
        self._histo_cache: Dict[Tuple[str, frozenset], Dict] = {}     # Track histogram state
        self._histo_pending: defaultdict = defaultdict(list)           # Queue observations
        self._lock = threading.Lock()  # Thread-safe state updates
        self._req_seq = 0  # Debug request sequence number

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ts(self, ts):
        """
        Normalize timestamp to milliseconds since epoch.

        Args:
            ts: Unix timestamp (seconds or ms), or None for current time

        Returns:
            Timestamp in milliseconds
        """
        if ts is None:
            return int(time.time() * 1000)
        # Auto-detect if timestamp is in seconds or milliseconds
        return int(ts * 1000) if ts < 10**12 else int(ts)

    def _fmt_labels(self, labels: Dict) -> str:
        """
        Format labels dict as Prometheus-style string for debug output.

        Args:
            labels: Dict of label key-value pairs

        Returns:
            Formatted string like {key:"value",key2:"value2"}
        """
        if not labels:
            return ""
        return "{" + ",".join(f'{k}:"{v}"' for k, v in labels.items()) + "}"

    def _labels_dict(self, ts):
        """
        Extract metric name and labels from a TimeSeries protobuf.

        Args:
            ts: TimeSeries protobuf message

        Returns:
            Tuple of (metric_name, labels_dict)
        """
        metric = None
        labels = {}
        for l in ts.labels:
            if l.name == "__name__":
                metric = l.value
            else:
                labels[l.name] = l.value
        return metric, labels

    def _is_histo(self, metric: str) -> bool:
        """
        Check if a metric name belongs to a histogram.

        Histograms in Prometheus consist of three metric types:
        - metric_bucket: cumulative counters for observation buckets
        - metric_sum: sum of all observed values
        - metric_count: total number of observations
        """
        return metric.endswith("_bucket") or metric.endswith("_sum") or metric.endswith("_count")

    # ------------------------------------------------------------------
    # Debug print (Prometheus /metrics style; no HELP; no timestamp)
    # ------------------------------------------------------------------

    def _debug_print(self, wr):
        """
        Print WriteRequest in Prometheus exposition format for debugging.
        This helps verify the metrics before they are sent to the remote endpoint.
        """
        if not self.debug:
            return

        self._req_seq += 1
        print(f"[DEBUG] remote_write_req_seq: {self._req_seq}")

        counters = []
        gauges = []
        histos = []

        # Classify timeseries by metric type
        for ts in wr.timeseries:
            metric, _ = self._labels_dict(ts)
            if self._is_histo(metric or ""):
                histos.append(ts)
            elif metric.endswith("_total"):
                counters.append(ts)
            else:
                gauges.append(ts)

        # ---- COUNTERS ----------------------------------------------------
        # Counters are monotonically increasing values (e.g., total requests)
        for ts in counters:
            metric, labels = self._labels_dict(ts)
            print(f"# TYPE {metric} counter")
            for sm in ts.samples:
                val = int(sm.value) if float(sm.value).is_integer() else sm.value
                print(f"{metric}{self._fmt_labels(labels)} {val}")
            print()

        # ---- GAUGES ------------------------------------------------------
        # Gauges are arbitrary values that can go up or down (e.g., queue depth)
        for ts in gauges:
            metric, labels = self._labels_dict(ts)
            print(f"# TYPE {metric} gauge")
            for sm in ts.samples:
                val = int(sm.value) if float(sm.value).is_integer() else sm.value
                print(f"{metric}{self._fmt_labels(labels)} {val}")
            print()

        # ---- HISTOGRAM ---------------------------------------------------
        # Histograms consist of _bucket, _sum, and _count metrics
        if histos:
            # Group by base name (only for printing TYPE line and sorting, not merging values)
            base_name = None
            buckets = []
            sums = []
            counts = []

            # Separate histogram components
            for ts in histos:
                metric, labels = self._labels_dict(ts)
                if metric.endswith("_bucket"):
                    buckets.append(ts)
                    base_name = metric[: -len("_bucket")]
                elif metric.endswith("_sum"):
                    sums.append(ts)
                    base_name = metric[: -len("_sum")]
                elif metric.endswith("_count"):
                    counts.append(ts)
                    base_name = metric[: -len("_count")]

            if base_name:
                print(f"# TYPE {base_name} histogram")

            # Sort buckets by 'le' label (ascending order, +Inf last)
            def sort_le(ts):
                _, labels = self._labels_dict(ts)
                le = labels.get("le")
                if le == "+Inf":
                    return float("inf")
                try:
                    return float(le)
                except Exception:
                    return float("inf")

            buckets.sort(key=sort_le)

            # Print buckets (only last sample value)
            for ts in buckets:
                metric, labels = self._labels_dict(ts)
                val = ts.samples[-1].value if ts.samples else None
                if val is not None and float(val).is_integer():
                    val = int(val)
                print(f"{metric}{self._fmt_labels(labels)} {val}")

            # Print count (total number of observations)
            for ts in counts:
                metric, labels = self._labels_dict(ts)
                val = ts.samples[-1].value if ts.samples else None
                if val is not None and float(val).is_integer():
                    val = int(val)
                print(f"{metric}{self._fmt_labels(labels)} {val}")

            # Print sum (sum of all observed values)
            for ts in sums:
                metric, labels = self._labels_dict(ts)
                val = ts.samples[-1].value if ts.samples else None
                if val is not None and float(val).is_integer():
                    val = int(val)
                print(f"{metric}{self._fmt_labels(labels)} {val}")

            print()

    # ------------------------------------------------------------------
    def _post(self, wr):
        """
        Serialize, compress, and POST the WriteRequest to the remote endpoint.

        Args:
            wr: WriteRequest protobuf message

        Returns:
            requests.Response object

        Raises:
            requests.HTTPError: If the request fails
        """
        self._debug_print(wr)
        # Serialize protobuf message to binary format
        payload = wr.SerializeToString()
        # POST with Snappy compression (required by Prometheus remote_write spec)
        r = self._sess.post(
            self.endpoint,
            data=snappy.compress(payload),
            headers=self.headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r

    # ------------------------------------------------------------------
    # Gauge / Counter
    # ------------------------------------------------------------------

    def send_gauge(self, metric: str, value, labels: Dict | None = None, ts=None):
        """
        Send a gauge metric (a value that can go up or down).

        Examples: temperature, memory usage, queue depth

        Args:
            metric: Metric name (e.g., "queue_depth")
            value: Current value
            labels: Optional dict of label key-value pairs
            ts: Optional timestamp (seconds or ms), defaults to now

        Returns:
            HTTP response object
        """
        L, S, TS, WR = self._Label, self._Sample, self._TimeSeries, self._WriteRequest
        ts_ms = self._ts(ts)
        # Build label list with __name__ label for the metric name
        lbls = [L(name="__name__", value=metric)] + [
            L(name=k, value=str(v)) for k, v in (labels or {}).items()
        ]
        return self._post(
            WR(timeseries=[TS(labels=lbls, samples=[S(value=float(value), timestamp=ts_ms)])])
        )

    def counter_add(self, metric_base: str, inc, labels: Dict | None = None, ts=None):
        """
        Increment a counter metric (monotonically increasing value).

        Counters automatically append "_total" suffix per Prometheus convention.
        The client maintains state to ensure monotonic increases.

        Examples: http_requests, bytes_processed, errors

        Args:
            metric_base: Metric name without "_total" suffix
            inc: Value to increment by
            labels: Optional dict of label key-value pairs
            ts: Optional timestamp (seconds or ms), defaults to now

        Returns:
            HTTP response object
        """
        metric = metric_base + "_total"
        # Use (metric, labels) as cache key
        key = (metric, frozenset((labels or {}).items()))
        with self._lock:
            # Add increment to cached value to maintain monotonicity
            newv = self._counter_cache.get(key, 0.0) + float(inc)
            self._counter_cache[key] = newv
        return self.send_gauge(metric, newv, labels, ts)

    # ------------------------------------------------------------------
    # Histogram queue + flush
    # ------------------------------------------------------------------

    def histogram_queue(self, metric_base: str, value: float, labels=None, ts=None):
        """
        Queue an observation for a histogram metric.

        Observations are queued in-memory until histogram_flush() is called.
        This allows batching multiple observations into a single remote_write request.

        Args:
            metric_base: Metric name without suffix (e.g., "request_duration_seconds")
            value: Observed value
            labels: Optional dict of label key-value pairs
            ts: Optional timestamp (seconds or ms), defaults to now
        """
        key = (metric_base, frozenset((labels or {}).items()))
        self._histo_pending[key].append((float(value), self._ts(ts)))

    @staticmethod
    def _cumulate(bks: List[int], n: int) -> List[int]:
        """
        Convert non-cumulative bucket counts to cumulative counts.

        Prometheus histograms use cumulative buckets, where each bucket
        contains the count of all observations <= its upper bound.

        Args:
            bks: Non-cumulative bucket counts
            n: Number of finite buckets (excluding +Inf)

        Returns:
            List of cumulative counts including +Inf bucket
        """
        out = []
        run = 0
        for i in range(n):
            run += bks[i]
            out.append(run)
        out.append(run + bks[-1])  # +Inf bucket (equals total count)
        return out

    def histogram_flush(self, metric_base: str, labels=None, bounds=None):
        """
        Flush queued histogram observations and send to remote endpoint.

        This method:
        1. Processes all queued observations for this histogram
        2. Updates bucket counts, sum, and count
        3. Generates cumulative bucket counts per Prometheus spec
        4. Creates _bucket, _sum, and _count timeseries
        5. Sends all timeseries in a single WriteRequest

        Histogram state is maintained across flushes for correct cumulative values.

        Args:
            metric_base: Metric name without suffix
            labels: Optional dict of label key-value pairs (must match queue calls)
            bounds: List of bucket upper bounds (e.g., [0.5, 1, 2.5, 5, 10])
                   Default: [0.5, 1, 2.5, 5, 10]
                   An implicit +Inf bucket is always added

        Returns:
            HTTP response object, or None if no observations are queued
        """
        if bounds is None:
            bounds = [0.5, 1, 2.5, 5, 10]

        key = (metric_base, frozenset((labels or {}).items()))
        vts = self._histo_pending.get(key)
        if not vts:
            return None

        # Sort observations by timestamp for correct time-series ordering
        vts.sort(key=lambda x: x[1])
        L, S, TS, WR = self._Label, self._Sample, self._TimeSeries, self._WriteRequest

        with self._lock:
            # Initialize or retrieve histogram state
            st = self._histo_cache.get(key)
            if st is None:
                st = {
                    "bounds": list(bounds),
                    "buckets": [0] * (len(bounds) + 1),  # +1 for +Inf bucket
                    "sum": 0.0,
                    "count": 0,
                }
                self._histo_cache[key] = st

            bks = list(st["buckets"])
            tsum = float(st["sum"])
            tcnt = int(st["count"])
            snaps = []  # Snapshots: (timestamp, non_cumulative_buckets, sum, count)

            # Process each observation
            for val, ts in vts:
                tsum += val
                tcnt += 1
                placed = False
                # Place observation in appropriate bucket
                for i, b in enumerate(st["bounds"]):
                    if val <= b:
                        bks[i] += 1
                        placed = True
                        break
                # If value exceeds all bounds, place in +Inf bucket
                if not placed:
                    bks[-1] += 1
                # Capture snapshot after this observation
                snaps.append((ts, list(bks), tsum, tcnt))

            # Update persistent state
            st["buckets"] = bks
            st["sum"] = tsum
            st["count"] = tcnt

        # Clear pending queue after processing
        self._histo_pending[key].clear()

        # Convert snapshots to cumulative buckets
        snaps_cum = [(ts, self._cumulate(b, len(bounds)), s, c) for ts, b, s, c in snaps]
        series = []

        # Create timeseries for each finite bucket
        for i, b in enumerate(bounds):
            lbls = [L(name="__name__", value=f"{metric_base}_bucket")]
            for k, v in (labels or {}).items():
                lbls.append(L(name=k, value=str(v)))
            lbls.append(L(name="le", value=str(b)))  # "le" = less than or equal
            samples = [S(value=float(cb[i]), timestamp=ts) for ts, cb, _, _ in snaps_cum]
            series.append(TS(labels=lbls, samples=samples))

        # Create timeseries for +Inf bucket (equals total count)
        lbls = [L(name="__name__", value=f"{metric_base}_bucket")]
        for k, v in (labels or {}).items():
            lbls.append(L(name=k, value=str(v)))
        lbls.append(L(name="le", value="+Inf"))
        samples = [S(value=float(c), timestamp=ts) for ts, _, _, c in snaps_cum]
        series.append(TS(labels=lbls, samples=samples))

        # Create _sum and _count timeseries
        for suffix, idx in (("_sum", 2), ("_count", 3)):
            lbls = [L(name="__name__", value=f"{metric_base}{suffix}")]
            for k, v in (labels or {}).items():
                lbls.append(L(name=k, value=str(v)))
            samples = [S(value=float(snap[idx]), timestamp=snap[0]) for snap in snaps_cum]
            series.append(TS(labels=lbls, samples=samples))

        return self._post(WR(timeseries=series))


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example endpoint (replace with your actual Prometheus remote_write URL)
    ENDPOINT = "https://prometheus/api/v1/write"

    # Create client with debug mode to see metrics before sending
    cli = RemoteWriteClient(ENDPOINT, debug=True)

    # Example 1: Counter - tracks total billing orders processed
    cli.counter_add("billing_orders", 85)

    # Example 2: Gauges - track current queue depths
    cli.send_gauge("billing_queue_depth", 36, {"queue": "payments"})
    cli.send_gauge("billing_queue_depth", 5,  {"queue": "refunds"})
    cli.send_gauge("billing_queue_depth", 0,  {"queue": "dlq"})

    # Example 3: Histograms - track job duration distributions
    # Queue observations with explicit timestamps
    now = int(time.time() * 1000)
    cli.histogram_queue("billing_job_duration_seconds", 0.6,  {"worker": "billing-worker-01"}, ts=now - 120000)
    cli.histogram_queue("billing_job_duration_seconds", 2.2,  {"worker": "billing-worker-01"}, ts=now - 60000)
    cli.histogram_queue("billing_job_duration_seconds", 10.0, {"worker": "billing-worker-01"}, ts=now)
    # Flush to send all queued observations for worker-01
    cli.histogram_flush("billing_job_duration_seconds", {"worker": "billing-worker-01"})

    # Same for worker-02
    cli.histogram_queue("billing_job_duration_seconds", 0.3,  {"worker": "billing-worker-02"}, ts=now - 120000)
    cli.histogram_queue("billing_job_duration_seconds", 1.2,  {"worker": "billing-worker-02"}, ts=now - 60000)
    cli.histogram_queue("billing_job_duration_seconds", 8.9, {"worker": "billing-worker-02"}, ts=now)
    cli.histogram_flush("billing_job_duration_seconds", {"worker": "billing-worker-02"})

    print("[INFO] done")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
# [DEBUG] remote_write_req_seq: 1
# # TYPE billing_orders_total counter
# billing_orders_total 85
#
# [DEBUG] remote_write_req_seq: 2
# # TYPE billing_queue_depth gauge
# billing_queue_depth{queue:"payments"} 36
#
# [DEBUG] remote_write_req_seq: 3
# # TYPE billing_queue_depth gauge
# billing_queue_depth{queue:"refunds"} 5
#
# [DEBUG] remote_write_req_seq: 4
# # TYPE billing_queue_depth gauge
# billing_queue_depth{queue:"dlq"} 0
#
# [DEBUG] remote_write_req_seq: 5
# # TYPE billing_job_duration_seconds histogram
# billing_job_duration_seconds_bucket{worker:"billing-worker-01",le:"0.5"} 0
# billing_job_duration_seconds_bucket{worker:"billing-worker-01",le:"1"} 1
# billing_job_duration_seconds_bucket{worker:"billing-worker-01",le:"2.5"} 2
# billing_job_duration_seconds_bucket{worker:"billing-worker-01",le:"5"} 2
# billing_job_duration_seconds_bucket{worker:"billing-worker-01",le:"10"} 3
# billing_job_duration_seconds_bucket{worker:"billing-worker-01",le:"+Inf"} 3
# billing_job_duration_seconds_count{worker:"billing-worker-01"} 3
# billing_job_duration_seconds_sum{worker:"billing-worker-01"} 12.8
#
# [DEBUG] remote_write_req_seq: 6
# # TYPE billing_job_duration_seconds histogram
# billing_job_duration_seconds_bucket{worker:"billing-worker-02",le:"0.5"} 1
# billing_job_duration_seconds_bucket{worker:"billing-worker-02",le:"1"} 1
# billing_job_duration_seconds_bucket{worker:"billing-worker-02",le:"2.5"} 2
# billing_job_duration_seconds_bucket{worker:"billing-worker-02",le:"5"} 2
# billing_job_duration_seconds_bucket{worker:"billing-worker-02",le:"10"} 3
# billing_job_duration_seconds_bucket{worker:"billing-worker-02",le:"+Inf"} 3
# billing_job_duration_seconds_count{worker:"billing-worker-02"} 3
# billing_job_duration_seconds_sum{worker:"billing-worker-02"} 10.4
#
# [INFO] done
