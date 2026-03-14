import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

class InterviewDatabase:
    def __init__(self, db_path='interviews.db'):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_name TEXT NOT NULL,
                    job_role TEXT DEFAULT 'software_engineer',
                    total_questions INTEGER DEFAULT 0,
                    completed_questions INTEGER DEFAULT 0,
                    overall_score REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'in_progress',
                    start_time TEXT,
                    end_time TEXT,
                    responses TEXT,  -- JSON string of responses
                    resume_analysis TEXT,  -- JSON string of resume analysis
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def create_interview(self, candidate_name, job_role='software_engineer'):
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO interviews (candidate_name, job_role, start_time, status)
                VALUES (?, ?, ?, ?)
            ''', (candidate_name, job_role, datetime.now().isoformat(), 'in_progress'))
            interview_id = cursor.lastrowid
            conn.commit()
            return interview_id

    def update_interview_score(self, interview_id, score, completed_questions, total_questions):
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE interviews
                SET overall_score = ?, completed_questions = ?, total_questions = ?,
                    end_time = ?, status = ?
                WHERE id = ?
            ''', (score, completed_questions, total_questions,
                  datetime.now().isoformat(), 'completed', interview_id))
            conn.commit()

    def save_responses(self, interview_id, responses):
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE interviews
                SET responses = ?
                WHERE id = ?
            ''', (json.dumps(responses), interview_id))
            conn.commit()

    def save_resume_analysis(self, interview_id, resume_analysis):
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE interviews
                SET resume_analysis = ?
                WHERE id = ?
            ''', (json.dumps(resume_analysis), interview_id))
            conn.commit()

    def get_interview(self, interview_id):
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM interviews WHERE id = ?', (interview_id,)).fetchone()
            if row:
                return dict(row)
            return None

    def get_all_interviews(self, limit=100, offset=0):
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM interviews
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset)).fetchall()
            return [dict(row) for row in rows]

    def get_interview_stats(self):
        with self.get_connection() as conn:
            stats = conn.execute('''
                SELECT
                    COUNT(*) as total_interviews,
                    AVG(overall_score) as avg_score,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_interviews,
                    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_interviews,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_interviews,
                    MAX(overall_score) as highest_score,
                    MIN(overall_score) as lowest_score,
                    AVG(CASE WHEN status = 'completed' THEN overall_score END) as avg_completed_score
                FROM interviews
            ''').fetchone()
            return dict(stats)

    def get_score_distribution(self):
        """Get score distribution for charting"""
        with self.get_connection() as conn:
            scores = conn.execute('''
                SELECT overall_score
                FROM interviews
                WHERE overall_score IS NOT NULL AND status = 'completed'
            ''').fetchall()

            distribution = {'0-2': 0, '2-4': 0, '4-6': 0, '6-8': 0, '8-10': 0}
            for row in scores:
                score = row[0]
                if score < 2:
                    distribution['0-2'] += 1
                elif score < 4:
                    distribution['2-4'] += 1
                elif score < 6:
                    distribution['4-6'] += 1
                elif score < 8:
                    distribution['6-8'] += 1
                else:
                    distribution['8-10'] += 1

            return distribution

    def get_recent_interviews(self, limit=10):
        """Get recent interviews for dashboard"""
        with self.get_connection() as conn:
            interviews = conn.execute('''
                SELECT * FROM interviews
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(row) for row in interviews]

    def get_job_role_stats(self):
        """Get statistics by job role"""
        with self.get_connection() as conn:
            stats = conn.execute('''
                SELECT
                    job_role,
                    COUNT(*) as total,
                    AVG(overall_score) as avg_score,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed
                FROM interviews
                GROUP BY job_role
                ORDER BY total DESC
            ''').fetchall()
            return [dict(row) for row in stats]

    def delete_interview(self, interview_id):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM interviews WHERE id = ?', (interview_id,))
            conn.commit()