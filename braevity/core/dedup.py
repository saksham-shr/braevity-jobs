import sqlite3

class DedupStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        cursor = self.conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS seen_jobs (
    url TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    found_at TEXT
)""")
        self.conn.commit()


    def is_seen(self, url):
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM seen_jobs WHERE url = ?", (url,))
        result = cursor.fetchone()
        return result is not None

    def mark_seen(self, job):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO seen_jobs (url, title, company, found_at) VALUES (?, ?, ?, ?)",
            (job.url, job.title, job.company, job.found_at)
        )
        self.conn.commit()

    def mark_seen_batch(self, jobs):
        cursor = self.conn.cursor()
        cursor.executemany(
            "INSERT OR IGNORE INTO seen_jobs (url, title, company, found_at) VALUES (?, ?, ?, ?)",
            [(job.url, job.title, job.company, job.found_at) for job in jobs]
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
        
