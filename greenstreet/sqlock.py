import os
from time import sleep

import sqlite3
from os.path import dirname


def get_db(db_file):
    db_dir = dirname(db_file)
    os.makedirs(db_dir, exist_ok=True)
    db = sqlite3.connect(
        db_file, detect_types=sqlite3.PARSE_DECLTYPES)
    db.row_factory = sqlite3.Row
    return db


def release_all_locks(db_file):
    db = get_db(db_file)
    db.execute('DELETE FROM locks;')
    db.close()


class SQLiteLock():
    def __init__(self, db_file, lock_name="global", blocking=False):
        self.db_file = db_file
        self.lock_name = lock_name
        self.lock_acquired = False
        self.acquire(blocking=blocking)

    def acquire(self, blocking=False):
        if self.lock_acquired:
            return

        if not os.path.isfile(self.db_file):
            self.init_db()

        while True and not self.lock_acquired:
            db = get_db(self.db_file)
            db.isolation_level = 'EXCLUSIVE'
            db.execute('BEGIN EXCLUSIVE')
            lock_entry = db.execute(
                'SELECT * FROM locks WHERE name = ?',
                (self.lock_name,)).fetchone()
            if lock_entry is None:
                db.execute(
                    'INSERT INTO locks (name) VALUES (?)',
                    (self.lock_name,))
                self.lock_acquired = True
            db.commit()
            db.close()
            if self.lock_acquired or not blocking:
                break
            sleep(0.4)

    def init_db(self):
        db = get_db(self.db_file)
        db.executescript('DROP TABLE IF EXISTS locks; '
                         'CREATE TABLE locks (name TEXT NOT NULL);')
        db.close()

    def locked(self):
        return self.lock_acquired

    def __enter__(self):
        return self

    def __exit__(self, *_, **__):
        self.release()

    def release(self):
        if not self.locked():
            return
        db = get_db(self.db_file)
        db.execute(
            'DELETE FROM locks WHERE name = ?',
            (self.lock_name,))
        db.commit()
        db.close()
        self.lock_acquired = False