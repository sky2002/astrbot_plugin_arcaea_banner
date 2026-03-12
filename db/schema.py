"""负责初始化和升级插件使用的 SQLite 表结构。"""

from __future__ import annotations

import sqlite3


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """读取指定数据表当前已有的字段集合。"""
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str):
    """在字段缺失时为现有数据表补充列定义。"""
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def ensure_schema(conn: sqlite3.Connection):
    """初始化插件所需的数据表，并补齐兼容旧版本的字段。"""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_key TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS charts (
            chart_id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_name TEXT NOT NULL,
            pack_name TEXT NOT NULL,
            version_group TEXT NOT NULL,
            version_text TEXT,
            difficulty TEXT NOT NULL,
            level_text TEXT,
            constant REAL NOT NULL,
            note_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(song_name, pack_name, difficulty)
        );

        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_key TEXT NOT NULL,
            chart_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_chart_best (
            user_key TEXT NOT NULL,
            chart_id INTEGER NOT NULL,
            best_score INTEGER NOT NULL,
            play_count INTEGER NOT NULL DEFAULT 1,
            last_score INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_key, chart_id)
        );

        CREATE TABLE IF NOT EXISTS chart_aliases (
            alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
            chart_id INTEGER NOT NULL,
            alias_name TEXT NOT NULL,
            alias_norm TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1.0,
            created_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_chart_aliases_chart_norm
        ON chart_aliases(chart_id, alias_norm);

        CREATE INDEX IF NOT EXISTS idx_chart_aliases_norm
        ON chart_aliases(alias_norm);
        """
    )

    _ensure_column(conn, "charts", "version_text", "TEXT")
    _ensure_column(conn, "charts", "level_text", "TEXT")
    _ensure_column(conn, "charts", "note_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "user_chart_best", "last_score", "INTEGER NOT NULL DEFAULT 0")

    conn.commit()
