"""
Persistent SQLite Audit Logger for DCRG Phase 8.
Records chronological lifecycle events across Voice, Joystick, Synchronization,
Fusion, Safety Authorization, Command Execution, Emergency Stops, and Configuration Changes.
Compliant with DCRG-ARCH-005.
"""

import csv
import io
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

logger = logging.getLogger(__name__)

# Default database location in the backend directory
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "dcrg_audit.db"
)


class AuditLogger:
    """
    Thread-safe SQLite persistent audit trail manager for DCRG.
    Maintains forensic records of all multi-modal inputs, safety decisions,
    gateway dispatches, emergency stops, and configuration mutations.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.abspath(DEFAULT_DB_PATH)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a SQLite connection configured for WAL mode."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Initializes database schema and indexes."""
        with self._lock:
            try:
                conn = self._get_connection()
                with conn:
                    # 1. Main Audit Events Table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS audit_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            event_id TEXT NOT NULL,
                            timestamp_ms REAL NOT NULL,
                            iso_time TEXT NOT NULL,
                            category TEXT NOT NULL,
                            command TEXT,
                            safety_state TEXT,
                            execution_result TEXT,
                            crs REAL,
                            details_json TEXT
                        );
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events (timestamp_ms DESC);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_category ON audit_events (category);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_state ON audit_events (safety_state);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_cmd ON audit_events (command);")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_result ON audit_events (execution_result);")

                    # 2. Configuration Audit History Table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS config_audit (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp_ms REAL NOT NULL,
                            iso_time TEXT NOT NULL,
                            operator_id TEXT NOT NULL,
                            parameter_name TEXT NOT NULL,
                            old_value TEXT,
                            new_value TEXT,
                            reason TEXT
                        );
                    """)
                conn.close()
                logger.info("DCRG SQLite Audit Logger initialized at: %s", self.db_path)
            except Exception as e:
                logger.error("Failed to initialize SQLite Audit Database: %s", e)

    def log_event(
        self,
        category: str,
        command: Optional[str] = None,
        safety_state: Optional[str] = None,
        execution_result: Optional[str] = None,
        crs: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        timestamp_ms: Optional[float] = None,
    ) -> str:
        """
        Inserts an immutable audit event record.
        Returns the event UUID.
        """
        eid = event_id or str(uuid4())
        ts_ms = timestamp_ms if timestamp_ms is not None else (time.time() * 1000.0)
        iso_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts_ms / 1000.0)) + f".{int(ts_ms % 1000):03d}Z"
        details_str = json.dumps(details or {}, default=str)

        with self._lock:
            try:
                conn = self._get_connection()
                with conn:
                    conn.execute("""
                        INSERT INTO audit_events (
                            event_id, timestamp_ms, iso_time, category, command,
                            safety_state, execution_result, crs, details_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        eid, ts_ms, iso_str, category.upper(), command,
                        safety_state.upper() if safety_state else None,
                        execution_result.upper() if execution_result else None,
                        round(crs, 2) if crs is not None else None,
                        details_str
                    ))
                conn.close()
            except Exception as e:
                logger.error("Error writing audit event (%s): %s", category, e)
        return eid

    def log_config_change(
        self,
        parameter_name: str,
        old_value: Any,
        new_value: Any,
        operator_id: str = "OP-PRIMARY",
        reason: Optional[str] = None,
    ) -> None:
        """Records an auditable configuration change."""
        now_ms = time.time() * 1000.0
        iso_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ms / 1000.0))

        with self._lock:
            try:
                conn = self._get_connection()
                with conn:
                    conn.execute("""
                        INSERT INTO config_audit (
                            timestamp_ms, iso_time, operator_id, parameter_name,
                            old_value, new_value, reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (
                        now_ms, iso_str, operator_id, parameter_name,
                        str(old_value), str(new_value), reason or "Manual update"
                    ))
                conn.close()
            except Exception as e:
                logger.error("Error logging configuration change: %s", e)

    def query_logs(
        self,
        category: Optional[str] = None,
        safety_state: Optional[str] = None,
        command: Optional[str] = None,
        execution_result: Optional[str] = None,
        start_time_ms: Optional[float] = None,
        end_time_ms: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Queries persistent audit logs with comprehensive filtering.
        """
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: List[Any] = []

        if category and category.upper() != "ALL":
            query += " AND category = ?"
            params.append(category.upper())

        if safety_state and safety_state.upper() != "ALL":
            query += " AND safety_state = ?"
            params.append(safety_state.upper())

        if command and command.upper() != "ALL":
            query += " AND command = ?"
            params.append(command.upper())

        if execution_result and execution_result.upper() != "ALL":
            query += " AND execution_result = ?"
            params.append(execution_result.upper())

        if start_time_ms is not None:
            query += " AND timestamp_ms >= ?"
            params.append(start_time_ms)

        if end_time_ms is not None:
            query += " AND timestamp_ms <= ?"
            params.append(end_time_ms)

        query += " ORDER BY timestamp_ms DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 1000)), max(0, offset)])

        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    row_dict = dict(r)
                    if row_dict.get("details_json"):
                        try:
                            row_dict["details"] = json.loads(row_dict["details_json"])
                        except Exception:
                            row_dict["details"] = {}
                    else:
                        row_dict["details"] = {}
                    results.append(row_dict)
                conn.close()
                return results
            except Exception as e:
                logger.error("Error querying audit logs: %s", e)
                return []

    def export_logs(
        self,
        format_type: str = "json",
        category: Optional[str] = None,
        safety_state: Optional[str] = None,
        command: Optional[str] = None,
        execution_result: Optional[str] = None,
        limit: int = 1000,
    ) -> str:
        """
        Exports audit records as formatted JSON or CSV string.
        """
        records = self.query_logs(
            category=category,
            safety_state=safety_state,
            command=command,
            execution_result=execution_result,
            limit=limit,
        )

        if format_type.lower() == "csv":
            output = io.StringIO()
            fieldnames = [
                "id", "event_id", "timestamp_ms", "iso_time", "category",
                "command", "safety_state", "execution_result", "crs", "details_json"
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                writer.writerow(rec)
            return output.getvalue()
        else:
            return json.dumps(records, indent=2, default=str)

    def get_counts(self) -> Dict[str, Any]:
        """Returns aggregate event counts across categories and safety states."""
        with self._lock:
            try:
                conn = self._get_connection()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM audit_events;")
                total = c.fetchone()[0]

                c.execute("SELECT category, COUNT(*) FROM audit_events GROUP BY category;")
                category_counts = {r[0]: r[1] for r in c.fetchall()}

                c.execute("SELECT safety_state, COUNT(*) FROM audit_events WHERE safety_state IS NOT NULL GROUP BY safety_state;")
                state_counts = {r[0]: r[1] for r in c.fetchall()}

                conn.close()
                return {
                    "total_events": total,
                    "categories": category_counts,
                    "states": state_counts,
                    "db_path": self.db_path,
                }
            except Exception as e:
                logger.error("Error retrieving audit counts: %s", e)
                return {"total_events": 0, "categories": {}, "states": {}, "db_path": self.db_path}


# Global Singleton Instance
audit_logger = AuditLogger()

