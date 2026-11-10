"""SQLite local persistence for SAVIA; never fabricates sensor readings."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "storage"
DB = STORE / "savia.sqlite3"

@contextmanager
def connect():
    STORE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init():
    (STORE / 'photos').mkdir(parents=True, exist_ok=True)
    (STORE / 'models').mkdir(parents=True, exist_ok=True)
    (STORE / 'uploads').mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS plants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, species TEXT NOT NULL,
                zone TEXT NOT NULL DEFAULT '', planted_at TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER REFERENCES plants(id) ON DELETE CASCADE,
                temperature REAL, humidity REAL, soil_moisture REAL,
                light REAL, ph REAL, source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
                filename TEXT NOT NULL, label TEXT NOT NULL DEFAULT '',
                green_fraction REAL, yellow_fraction REAL, brown_fraction REAL,
                sharpness REAL, note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        ''')

def log(category, title, detail=''):
    with connect() as c:
        c.execute('INSERT INTO activity(category,title,detail) VALUES(?,?,?)',(category,title,detail))

def rows(sql, args=()):
    with connect() as c:
        return [dict(r) for r in c.execute(sql,args).fetchall()]
