"""Durable account-scoped receipts, encrypted tokens, and one-use intents."""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
import secrets
import sqlite3

from cryptography.fernet import Fernet, InvalidToken


def digest(value):
    return sha256(value.encode()).hexdigest()


class Store:
    def __init__(self, path, encryption_key):
        self.path = path
        self.fernet = Fernet(encryption_key.encode())
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS oauth (
                  state TEXT PRIMARY KEY, binding TEXT NOT NULL, mode TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                  id TEXT PRIMARY KEY, account_key TEXT NOT NULL, mode TEXT NOT NULL,
                  secret BLOB NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS previews (
                  id TEXT PRIMARY KEY, account_key TEXT NOT NULL, session_id TEXT NOT NULL,
                  symbol TEXT NOT NULL, state TEXT NOT NULL, expires REAL NOT NULL,
                  client_order_id TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, result TEXT);
                CREATE INDEX IF NOT EXISTS preview_account ON previews(account_key,state);
                CREATE TABLE IF NOT EXISTS fills (
                  account_key TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL,
                  PRIMARY KEY(account_key,id));
            """)
        os.chmod(path, 0o600)

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def oauth_begin(self, mode, now):
        state, binding = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute("DELETE FROM oauth WHERE expires <= ?", (now,))
            db.execute("INSERT INTO oauth VALUES (?,?,?,?)", (digest(state), digest(binding), mode, now + 300))
        return state, binding

    def oauth_consume(self, state, binding, now):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM oauth WHERE state=?", (digest(state),)).fetchone()
            if not row or row["expires"] <= now or not secrets.compare_digest(row["binding"], digest(binding)):
                db.rollback()
                return None
            db.execute("DELETE FROM oauth WHERE state=?", (digest(state),))
            db.commit()
            return row["mode"]

    def session_create(self, mode, token, account_id, now, lifetime):
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        account_key = digest(mode + ":" + account_id)
        secret = self.fernet.encrypt(json.dumps({"token": token, "account_id": account_id}).encode())
        with self.db() as db:
            db.execute("DELETE FROM sessions WHERE expires<=?", (now,))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)", (digest(sid), account_key, mode, secret, csrf, now + lifetime))
        return sid, csrf

    def session(self, sid, now):
        if not sid:
            return None
        with self.db() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=? AND expires>?", (digest(sid), now)).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result.update(json.loads(self.fernet.decrypt(row["secret"])))
        except (InvalidToken, ValueError):
            return None
        result.pop("secret")
        return result

    def disconnect(self, session):
        with self.db() as db:
            # Invalidate all sessions for this account; receipts/fills remain private and recover on reconnect.
            db.execute("DELETE FROM sessions WHERE account_key=?", (session["account_key"],))
            db.execute("UPDATE previews SET state='canceled' WHERE account_key=? AND state='prepared'", (session["account_key"],))

    def preview_create(self, session, payload, now, lifetime):
        pid = secrets.token_urlsafe(24)
        cid = "spicy-" + digest(pid)[:40]
        with self.db() as db:
            db.execute("INSERT INTO previews VALUES (?,?,?,?,?,?,?,?,NULL)",
                       (pid, session["account_key"], session["id"], payload["symbol"], "prepared", now + lifetime, cid, json.dumps(payload)))
        return self.preview(session, pid)

    def preview(self, session, pid):
        with self.db() as db:
            row = db.execute("SELECT * FROM previews WHERE id=? AND account_key=? AND session_id=?",
                             (pid, session["account_key"], session["id"])).fetchone()
        return self.decode(row) if row else None

    @staticmethod
    def decode(row):
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        result["result"] = json.loads(result["result"]) if result["result"] else None
        return result

    def claim(self, session, pid, now):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM previews WHERE id=? AND account_key=? AND session_id=?",
                             (pid, session["account_key"], session["id"])).fetchone()
            if not row:
                db.rollback()
                return "missing", None
            record = self.decode(row)
            if record["state"] != "prepared":
                db.rollback()
                return "existing", record
            if record["expires"] <= now:
                db.execute("UPDATE previews SET state='expired' WHERE id=?", (pid,))
                db.commit()
                return "expired", record
            pending = db.execute("SELECT 1 FROM previews WHERE account_key=? AND state IN ('sending','unknown')", (session["account_key"],)).fetchone()
            if pending:
                db.rollback()
                return "unresolved", record
            db.execute("UPDATE previews SET state='sending' WHERE id=?", (pid,))
            db.commit()
            record["state"] = "sending"
            return "claimed", record

    def update(self, pid, state, result=None):
        with self.db() as db:
            db.execute("UPDATE previews SET state=?,result=? WHERE id=?", (state, json.dumps(result) if result is not None else None, pid))

    def pending(self, session):
        with self.db() as db:
            rows = db.execute("SELECT * FROM previews WHERE account_key=? AND state IN ('sending','unknown','accepted') ORDER BY expires DESC LIMIT 100", (session["account_key"],)).fetchall()
        return [self.decode(r) for r in rows]

    def save_fills(self, session, fills):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for f in fills:
                existing = db.execute("SELECT payload FROM fills WHERE account_key=? AND id=?", (session["account_key"], f["id"])).fetchone()
                encoded = json.dumps(f, sort_keys=True)
                if existing and existing["payload"] != encoded:
                    db.rollback()
                    raise ValueError("Broker activity changed: manual reconciliation required")
                db.execute("INSERT OR IGNORE INTO fills VALUES (?,?,?)", (session["account_key"], f["id"], encoded))
            db.commit()

    def fills(self, session):
        with self.db() as db:
            rows = db.execute("SELECT payload FROM fills WHERE account_key=? ORDER BY id DESC LIMIT 2001", (session["account_key"],)).fetchall()
        return [json.loads(r["payload"]) for r in rows[:2000]], len(rows) > 2000
