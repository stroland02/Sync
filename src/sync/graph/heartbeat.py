"""The run heartbeat: a process saying "still here" while the graph executes (B194).

A checkpoint records progress; this records existence. A run blocking inside `await_ci`
writes no checkpoint for as long as the customer's CI takes -- by design -- and until this
existed nothing distinguished it from a run that died, which the console refused to guess
about, on the record. The heartbeat measures the process rather than progress, so it ticks
straight through a CI wait.

A context manager rather than a callback set, because the property that matters is paired
setup and teardown: a run that raises still records its clean exit -- the *process* survived
to run the `finally`, and what failed is recorded by the pipeline as an outcome. Only a
process that dies stops ticking without `stopped_at`, and that is exactly the case the
expiry sweep exists to record.

Its own connection, deliberately: the tick runs on a timer thread, `GraphStore` holds one
psycopg connection for the life of the store, and psycopg connections are not thread-safe.
A dedicated autocommit connection per heartbeat keeps the tick from ever sharing a socket
with the pipeline's writes.
"""

from __future__ import annotations

import threading

import psycopg

HEARTBEAT_INTERVAL_SECS = 15
# Six missed ticks. Far above any healthy pause -- a loaded machine skips one, not six --
# and far below the hours a reader would otherwise spend not knowing.
EXPIRE_AFTER_SECS = 90


class RunHeartbeat:
    """Tick `run_heartbeat.last_heartbeat_at` for one thread while a `with` block runs."""

    def __init__(
        self,
        dsn: str,
        thread_id: str,
        *,
        interval_secs: float = HEARTBEAT_INTERVAL_SECS,
        expire_after_secs: int = EXPIRE_AFTER_SECS,
    ) -> None:
        self._dsn = dsn
        self._thread_id = thread_id
        self._interval = interval_secs
        self._expire_after = expire_after_secs
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None

    def __enter__(self) -> "RunHeartbeat":
        self._connection = psycopg.connect(self._dsn, autocommit=True)
        self._connection.execute(
            """
            INSERT INTO run_heartbeat (thread_id, expire_after_secs)
            VALUES (%s, %s)
            ON CONFLICT (thread_id) DO UPDATE SET
               started_at = now(),
               last_heartbeat_at = now(),
               expire_after_secs = EXCLUDED.expire_after_secs,
               stopped_at = NULL,
               expired_at = NULL
            """,
            [self._thread_id, self._expire_after],
        )
        self._worker = threading.Thread(target=self._tick, daemon=True)
        self._worker.start()
        return self

    def _tick(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._connection.execute(
                    "UPDATE run_heartbeat SET last_heartbeat_at = now() WHERE thread_id = %s",
                    [self._thread_id],
                )
            except psycopg.Error:
                # A tick that cannot reach the database must not kill the run it describes.
                # If the outage persists the sweep records EXPIRED, which is the honest
                # reading from outside: nothing was heard from this process.
                return

    def __exit__(self, *_exc) -> None:
        self._stop.set()
        if self._worker is not None:
            self._worker.join(timeout=5)
        try:
            self._connection.execute(
                "UPDATE run_heartbeat SET stopped_at = now() WHERE thread_id = %s",
                [self._thread_id],
            )
        finally:
            self._connection.close()
