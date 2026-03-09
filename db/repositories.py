from __future__ import annotations

import sqlite3
from datetime import datetime

from ..constants import DEFAULT_PLATFORM


class ArcaeaRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @staticmethod
    def now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    def ensure_user(self, user_key: str, sender_id: str, platform: str = DEFAULT_PLATFORM):
        now = self.now()
        row = self.conn.execute(
            "SELECT user_key FROM users WHERE user_key = ?",
            (user_key,),
        ).fetchone()

        if row:
            self.conn.execute(
                """
                UPDATE users
                SET updated_at = ?
                WHERE user_key = ?
                """,
                (now, user_key),
            )
        else:
            self.conn.execute(
                """
                INSERT INTO users (user_key, platform, sender_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_key, platform, sender_id or user_key, now, now),
            )
        self.conn.commit()

    def upsert_score(self, user_key: str, sender_id: str, chart_id: int, score: int, source: str = "image") -> dict:
        self.ensure_user(user_key=user_key, sender_id=sender_id)
        now = self.now()

        self.conn.execute(
            """
            INSERT INTO score_history (user_key, chart_id, score, source, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_key, chart_id, score, source, now),
        )

        row = self.conn.execute(
            """
            SELECT best_score, play_count, last_score
            FROM user_chart_best
            WHERE user_key = ? AND chart_id = ?
            """,
            (user_key, chart_id),
        ).fetchone()

        if row:
            old_best = int(row["best_score"])
            play_count = int(row["play_count"]) + 1
            new_best = max(old_best, score)
            self.conn.execute(
                """
                UPDATE user_chart_best
                SET best_score = ?, play_count = ?, last_score = ?, updated_at = ?
                WHERE user_key = ? AND chart_id = ?
                """,
                (new_best, play_count, score, now, user_key, chart_id),
            )
        else:
            old_best = 0
            play_count = 1
            new_best = score
            self.conn.execute(
                """
                INSERT INTO user_chart_best
                (user_key, chart_id, best_score, play_count, last_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_key, chart_id, score, 1, score, now),
            )

        self.conn.commit()
        return {
            "old_best": old_best,
            "new_best": new_best,
            "play_count": play_count,
        }


    def get_chart_by_id(self, chart_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM charts WHERE chart_id = ?",
            (chart_id,),
        ).fetchone()

    def get_user_chart_best_row(self, user_key: str, chart_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT
                b.user_key,
                b.chart_id,
                b.best_score,
                b.play_count,
                b.last_score,
                b.updated_at,
                c.song_name,
                c.pack_name,
                c.version_group,
                c.version_text,
                c.difficulty,
                c.level_text,
                c.constant,
                c.note_count
            FROM user_chart_best b
            JOIN charts c ON c.chart_id = b.chart_id
            WHERE b.user_key = ? AND b.chart_id = ?
            """,
            (user_key, chart_id),
        ).fetchone()

    def delete_user_chart(self, user_key: str, chart_id: int) -> dict:
        history_deleted = int(
            self.conn.execute(
                "DELETE FROM score_history WHERE user_key = ? AND chart_id = ?",
                (user_key, chart_id),
            ).rowcount or 0
        )
        best_deleted = int(
            self.conn.execute(
                "DELETE FROM user_chart_best WHERE user_key = ? AND chart_id = ?",
                (user_key, chart_id),
            ).rowcount or 0
        )
        self.conn.commit()
        return {
            "history_deleted": history_deleted,
            "best_deleted": best_deleted,
        }

    def get_total_chart_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS cnt FROM charts").fetchone()
        return int(row["cnt"] if row else 0)

    def get_chart_counts_by_difficulty(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT difficulty, COUNT(*) AS cnt FROM charts GROUP BY difficulty"
        ).fetchall()
        return {str(row["difficulty"]): int(row["cnt"]) for row in rows}

    def get_chart_counts_by_version(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT version_group, COUNT(*) AS cnt FROM charts GROUP BY version_group ORDER BY version_group"
        ).fetchall()
        return {str(row["version_group"]): int(row["cnt"]) for row in rows}

    def get_user_chart_rows(self, user_key: str) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT
                c.chart_id,
                c.song_name,
                c.pack_name,
                c.version_group,
                c.version_text,
                c.difficulty,
                c.level_text,
                c.constant,
                c.note_count,
                b.best_score,
                b.play_count,
                b.last_score,
                b.updated_at
            FROM user_chart_best b
            JOIN charts c ON c.chart_id = b.chart_id
            WHERE b.user_key = ?
            ORDER BY c.chart_id
            """,
            (user_key,),
        ).fetchall()
        return list(rows)

    def get_all_chart_rows(self) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT
                c.chart_id,
                c.song_name,
                c.pack_name,
                c.version_group,
                c.version_text,
                c.difficulty,
                c.level_text,
                c.constant,
                c.note_count
            FROM charts c
            ORDER BY c.chart_id
            """
        ).fetchall()
        return list(rows)

    def get_all_chart_rows_with_user_scores(self, user_key: str) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT
                c.chart_id,
                c.song_name,
                c.pack_name,
                c.version_group,
                c.version_text,
                c.difficulty,
                c.level_text,
                c.constant,
                c.note_count,
                COALESCE(b.best_score, 0) AS best_score,
                COALESCE(b.play_count, 0) AS play_count,
                COALESCE(b.last_score, 0) AS last_score,
                b.updated_at
            FROM charts c
            LEFT JOIN user_chart_best b
              ON c.chart_id = b.chart_id
             AND b.user_key = ?
            ORDER BY c.chart_id
            """,
            (user_key,),
        ).fetchall()
        return list(rows)

    def get_charts_by_difficulty(self, difficulty: str) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            "SELECT * FROM charts WHERE difficulty = ?",
            (difficulty,),
        ).fetchall()
        return list(rows)

    def find_exact_charts(self, song_name: str, difficulty: str, pack_name: str = "") -> list[sqlite3.Row]:
        if pack_name:
            rows = self.conn.execute(
                """
                SELECT *
                FROM charts
                WHERE difficulty = ?
                  AND song_name = ?
                  AND pack_name = ?
                """,
                (difficulty, song_name, pack_name),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT *
                FROM charts
                WHERE difficulty = ?
                  AND song_name = ?
                """,
                (difficulty, song_name),
            ).fetchall()
        return list(rows)

    def find_alias_rows_by_norm(self, difficulty: str, alias_norm: str) -> list[sqlite3.Row]:
        try:
            rows = self.conn.execute(
                """
                SELECT
                    c.*,
                    a.alias_name AS matched_alias_name,
                    a.alias_norm AS matched_alias_norm,
                    a.weight AS matched_alias_weight
                FROM chart_aliases a
                JOIN charts c ON c.chart_id = a.chart_id
                WHERE c.difficulty = ?
                  AND a.alias_norm = ?
                """,
                (difficulty, alias_norm),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return list(rows)

    def get_alias_rows_by_difficulty(self, difficulty: str) -> list[sqlite3.Row]:
        try:
            rows = self.conn.execute(
                """
                SELECT
                    c.*,
                    a.alias_name AS matched_alias_name,
                    a.alias_norm AS matched_alias_norm,
                    a.weight AS matched_alias_weight
                FROM chart_aliases a
                JOIN charts c ON c.chart_id = a.chart_id
                WHERE c.difficulty = ?
                """,
                (difficulty,),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        return list(rows)
