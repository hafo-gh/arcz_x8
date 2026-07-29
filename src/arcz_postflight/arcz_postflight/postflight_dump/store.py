"""Persistent, power-loss-resilient queues backed by SQLite.

Two logical queues live in one database:

* ``flights``  -- one row per qualifying flight, tracking collection state.
* ``uploads``  -- one row per produced zip, tracking resumable-upload state.

The database uses WAL journaling with ``synchronous=FULL`` so that a row is
durable on disk the moment a transaction commits -- important because the
companion computer may lose power at any time. A single connection is shared
across threads (the ROS callback thread enqueues; worker threads claim) and
guarded by a lock.
"""
import fcntl
import hashlib
import os
import sqlite3
import threading
import time
import uuid

# ---- flight (collection) states -------------------------------------------
PENDING_COLLECTION = 'pending_collection'
COLLECTING = 'collecting'
COLLECTED = 'collected'
COLLECTION_FAILED = 'collection_failed'

# ---- upload states ---------------------------------------------------------
PENDING_UPLOAD = 'pending_upload'
UPLOADING = 'uploading'
UPLOADED = 'uploaded'
UPLOAD_FAILED = 'upload_failed'

_SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_uuid    TEXT,
    arm_wall       REAL,
    disarm_wall    REAL,
    armed_duration REAL,
    created_at     REAL NOT NULL,
    status         TEXT NOT NULL,
    attempts       INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL NOT NULL DEFAULT 0,
    zip_path       TEXT,
    error          TEXT
);

CREATE TABLE IF NOT EXISTS uploads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id   INTEGER,
    flight_uuid TEXT,
    zip_path    TEXT NOT NULL,
    size        INTEGER NOT NULL,
    sha256      TEXT,
    offset      INTEGER NOT NULL DEFAULT 0,
    upload_url  TEXT,
    status      TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    error       TEXT,
    FOREIGN KEY (flight_id) REFERENCES flights (id)
);
"""


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Store:
    """Thread-safe SQLite-backed queue store."""

    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.RLock()
        init_lock_path = db_path + '.init.lock'
        with open(init_lock_path, 'a') as init_lock:
            fcntl.flock(init_lock.fileno(), fcntl.LOCK_EX)
            self._conn = sqlite3.connect(
                db_path, timeout=30.0, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            with self._lock:
                self._conn.execute('PRAGMA busy_timeout=30000')
                self._conn.execute('PRAGMA journal_mode=WAL')
                self._conn.execute('PRAGMA synchronous=FULL')
                self._conn.execute('PRAGMA foreign_keys=ON')
                self._conn.executescript(_SCHEMA)
                self._migrate()
                self._conn.commit()
            fcntl.flock(init_lock.fileno(), fcntl.LOCK_UN)

    def _columns(self, table):
        return {
            row['name']
            for row in self._conn.execute('PRAGMA table_info(%s)' % table)
        }

    def _migrate(self):
        """Add identity/retry columns to databases created by version 0.1."""
        flight_columns = self._columns('flights')
        if 'flight_uuid' not in flight_columns:
            self._conn.execute('ALTER TABLE flights ADD COLUMN flight_uuid TEXT')
        if 'next_attempt_at' not in flight_columns:
            self._conn.execute(
                'ALTER TABLE flights ADD COLUMN next_attempt_at REAL NOT NULL DEFAULT 0'
            )
        upload_columns = self._columns('uploads')
        if 'flight_uuid' not in upload_columns:
            self._conn.execute('ALTER TABLE uploads ADD COLUMN flight_uuid TEXT')
        if 'sha256' not in upload_columns:
            self._conn.execute('ALTER TABLE uploads ADD COLUMN sha256 TEXT')

        for row in self._conn.execute(
            'SELECT id FROM flights WHERE flight_uuid IS NULL OR flight_uuid=""'
        ).fetchall():
            self._conn.execute(
                'UPDATE flights SET flight_uuid=? WHERE id=?',
                (str(uuid.uuid4()), row['id']),
            )
        self._conn.execute(
            'UPDATE uploads SET flight_uuid=('
            'SELECT flight_uuid FROM flights WHERE flights.id=uploads.flight_id'
            ') WHERE flight_uuid IS NULL OR flight_uuid=""'
        )
        for row in self._conn.execute(
            'SELECT id, zip_path FROM uploads WHERE sha256 IS NULL OR sha256=""'
        ).fetchall():
            if os.path.isfile(row['zip_path']):
                self._conn.execute(
                    'UPDATE uploads SET sha256=? WHERE id=?',
                    (_sha256_file(row['zip_path']), row['id']),
                )

    def close(self):
        with self._lock:
            self._conn.close()

    # -- crash recovery ------------------------------------------------------
    def recover(self):
        """Revert in-progress rows to pending after an unclean shutdown.

        Uploads keep their persisted ``offset``/``upload_url`` so they resume
        instead of restarting. Returns (flights_reset, uploads_reset).
        """
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                'UPDATE flights SET status=? WHERE status=?',
                (PENDING_COLLECTION, COLLECTING),
            )
            flights_reset = cur.rowcount
            cur = self._conn.execute(
                'UPDATE uploads SET status=?, updated_at=? WHERE status=?',
                (PENDING_UPLOAD, now, UPLOADING),
            )
            uploads_reset = cur.rowcount
            self._conn.commit()
        return flights_reset, uploads_reset

    # -- collection queue ----------------------------------------------------
    def enqueue_flight(
        self, arm_wall, disarm_wall, armed_duration, initial_delay_s=0.0
    ):
        """Persist a new collection task immediately. Returns the flight id."""
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                'INSERT INTO flights '
                '(flight_uuid, arm_wall, disarm_wall, armed_duration, created_at, '
                'status, next_attempt_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    str(uuid.uuid4()), arm_wall, disarm_wall, armed_duration, now,
                    PENDING_COLLECTION, now + max(0.0, float(initial_delay_s)),
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def claim_next_collection(self, max_attempts):
        """Atomically claim the oldest pending flight; returns a dict or None."""
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM flights WHERE status=? AND attempts < ? '
                'AND next_attempt_at <= ? '
                'ORDER BY id ASC LIMIT 1',
                (PENDING_COLLECTION, max_attempts, time.time()),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                'UPDATE flights SET status=?, attempts=attempts+1 WHERE id=?',
                (COLLECTING, row['id']),
            )
            self._conn.commit()
            claimed = dict(row)
            claimed['status'] = COLLECTING
            claimed['attempts'] = row['attempts'] + 1
            return claimed

    def mark_collected(self, flight_id, zip_path, size):
        """Mark a flight collected and enqueue its zip for upload atomically."""
        now = time.time()
        with self._lock:
            flight = self._conn.execute(
                'SELECT flight_uuid FROM flights WHERE id=?', (flight_id,)
            ).fetchone()
            if flight is None:
                raise ValueError('unknown flight id %r' % flight_id)
            checksum = _sha256_file(zip_path)
            self._conn.execute(
                'UPDATE flights SET status=?, zip_path=?, error=NULL WHERE id=?',
                (COLLECTED, zip_path, flight_id),
            )
            self._conn.execute(
                'INSERT INTO uploads '
                '(flight_id, flight_uuid, zip_path, size, sha256, status, '
                'created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    flight_id, flight['flight_uuid'], zip_path, size, checksum,
                    PENDING_UPLOAD, now, now,
                ),
            )
            self._conn.commit()

    def mark_collection_failed(
        self, flight_id, error, max_attempts, retry_delay_s=0.0
    ):
        """Return a flight to pending, or park it as failed if out of attempts."""
        with self._lock:
            row = self._conn.execute(
                'SELECT attempts FROM flights WHERE id=?', (flight_id,)
            ).fetchone()
            attempts = row['attempts'] if row else max_attempts
            status = COLLECTION_FAILED if attempts >= max_attempts else PENDING_COLLECTION
            self._conn.execute(
                'UPDATE flights SET status=?, error=?, next_attempt_at=? WHERE id=?',
                (
                    status, str(error),
                    time.time() + max(0.0, float(retry_delay_s)),
                    flight_id,
                ),
            )
            self._conn.commit()

    # -- upload queue --------------------------------------------------------
    def claim_next_upload(self, max_attempts):
        """Atomically claim the oldest pending upload; returns a dict or None."""
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM uploads WHERE status=? AND attempts < ? '
                'ORDER BY id ASC LIMIT 1',
                (PENDING_UPLOAD, max_attempts),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                'UPDATE uploads SET status=?, attempts=attempts+1, updated_at=? '
                'WHERE id=?',
                (UPLOADING, time.time(), row['id']),
            )
            self._conn.commit()
            claimed = dict(row)
            claimed['status'] = UPLOADING
            claimed['attempts'] = row['attempts'] + 1
            return claimed

    def update_upload_progress(self, upload_id, offset, upload_url=None):
        """Persist resume state (byte offset + server upload URL) mid-transfer."""
        with self._lock:
            if upload_url is not None:
                self._conn.execute(
                    'UPDATE uploads SET offset=?, upload_url=?, updated_at=? '
                    'WHERE id=?',
                    (offset, upload_url, time.time(), upload_id),
                )
            else:
                self._conn.execute(
                    'UPDATE uploads SET offset=?, updated_at=? WHERE id=?',
                    (offset, time.time(), upload_id),
                )
            self._conn.commit()

    def mark_uploaded(self, upload_id):
        with self._lock:
            self._conn.execute(
                'UPDATE uploads SET status=?, error=NULL, updated_at=? WHERE id=?',
                (UPLOADED, time.time(), upload_id),
            )
            self._conn.commit()

    def mark_upload_failed(self, upload_id, error, max_attempts):
        """Return an upload to pending, or park it as failed if out of attempts."""
        with self._lock:
            row = self._conn.execute(
                'SELECT attempts FROM uploads WHERE id=?', (upload_id,)
            ).fetchone()
            attempts = row['attempts'] if row else max_attempts
            status = UPLOAD_FAILED if attempts >= max_attempts else PENDING_UPLOAD
            self._conn.execute(
                'UPDATE uploads SET status=?, error=?, updated_at=? WHERE id=?',
                (status, str(error), time.time(), upload_id),
            )
            self._conn.commit()

    # -- introspection -------------------------------------------------------
    def queue_sizes(self):
        """Return active (collection, upload) task counts.

        A task remains in its queue while it is pending (including retry
        backoff) or actively being processed. Completed and terminally failed
        rows are history, not queued work.
        """
        with self._lock:
            collecting = self._conn.execute(
                'SELECT COUNT(*) AS n FROM flights WHERE status IN (?, ?)',
                (PENDING_COLLECTION, COLLECTING),
            ).fetchone()['n']
            uploading = self._conn.execute(
                'SELECT COUNT(*) AS n FROM uploads WHERE status IN (?, ?)',
                (PENDING_UPLOAD, UPLOADING),
            ).fetchone()['n']
        return int(collecting), int(uploading)

    def counts(self):
        """Return {status: count} across both tables for logging/monitoring."""
        result = {}
        with self._lock:
            for table in ('flights', 'uploads'):
                for row in self._conn.execute(
                    'SELECT status, COUNT(*) AS n FROM %s GROUP BY status' % table
                ):
                    result[row['status']] = row['n']
        return result
