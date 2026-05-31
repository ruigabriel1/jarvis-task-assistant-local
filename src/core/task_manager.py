import os
import json
import sqlite3
import threading

class TaskManager:
    def __init__(self, filepath):
        # Translate .json to .db to ensure we always use SQLite
        if filepath.endswith('.json'):
            self.filepath = filepath[:-5] + '.db'
            self.json_filepath = filepath
        else:
            self.filepath = filepath
            self.json_filepath = filepath.replace('.db', '.json')

        self._lock = threading.RLock()
        self._init_db()
        self._migrate_if_needed()

    def _init_db(self):
        """Initialize the SQLite database and create the tasks table if it doesn't exist."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(self.filepath)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY,
                        text TEXT NOT NULL,
                        completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
                        priority TEXT NOT NULL,
                        sort_order INTEGER NOT NULL DEFAULT 0
                    )
                """)
                # Add sort_order to existing databases that don't have the column yet
                try:
                    conn.execute("ALTER TABLE tasks ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                # Initialize sort_order for rows still at 0 (migration from old schema)
                conn.execute("UPDATE tasks SET sort_order = id * 10 WHERE sort_order = 0")
                conn.commit()
            except Exception as e:
                print(f"[TaskManager] Error initializing database: {e}")
            finally:
                if conn:
                    conn.close()

    def _migrate_if_needed(self):
        """Migrate tasks from the old tasks.json file to the SQLite database if the JSON file exists."""
        with self._lock:
            if os.path.exists(self.json_filepath):
                try:
                    # Check if database already has tasks
                    existing_tasks = self.read_tasks()
                    if not existing_tasks:
                        with open(self.json_filepath, 'r', encoding='utf-8') as f:
                            tasks = json.load(f)
                        if isinstance(tasks, list) and tasks:
                            self.write_tasks(tasks)
                            print(f"[TaskManager] Successfully migrated {len(tasks)} tasks from JSON to SQLite.")
                    
                    # Rename the json file to tasks.json.bak to prevent future migration attempts
                    bak_path = self.json_filepath + '.bak'
                    if os.path.exists(bak_path):
                        try:
                            os.remove(bak_path)
                        except OSError as e:
                            print(f"[TaskManager] Error removing old bak file: {e}")
                    os.rename(self.json_filepath, bak_path)
                    print(f"[TaskManager] Archived old JSON file to {bak_path}")
                except Exception as e:
                    print(f"[TaskManager] Error migrating tasks from JSON: {e}")

    def read_tasks(self):
        """Thread-safe read from the SQLite database."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(self.filepath)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, text, completed, priority, sort_order FROM tasks")
                rows = cursor.fetchall()
                tasks = []
                for row in rows:
                    tasks.append({
                        "id": row["id"],
                        "text": row["text"],
                        "completed": bool(row["completed"]),
                        "priority": row["priority"],
                        "sort_order": row["sort_order"]
                    })
                return tasks
            except Exception as e:
                print(f"[TaskManager] Error reading tasks from SQLite: {e}")
                return []
            finally:
                if conn:
                    conn.close()

    def write_tasks(self, tasks):
        """Thread-safe and atomic write to the SQLite database."""
        with self._lock:
            conn = None
            try:
                conn = sqlite3.connect(self.filepath)
                conn.execute("BEGIN TRANSACTION")
                for t in tasks:
                    conn.execute(
                        "INSERT OR REPLACE INTO tasks (id, text, completed, priority, sort_order) VALUES (?, ?, ?, ?, ?)",
                        (t["id"], t["text"], 1 if t["completed"] else 0, t["priority"], t.get("sort_order", t["id"] * 10))
                    )
                conn.commit()
                return True
            except Exception as e:
                print(f"[TaskManager] Error writing tasks to SQLite: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except sqlite3.Error as re:
                        print(f"[TaskManager] Error rolling back: {re}")
                return False
            finally:
                if conn:
                    conn.close()

    def update_tasks(self, modify_callback):
        """Thread-safe and atomic read-modify-write cycle."""
        with self._lock:
            tasks = self.read_tasks()
            # Snapshot the old state before the callback potentially mutates the dictionaries
            old_tasks_map = {t["id"]: dict(t) for t in tasks}
            
            modified_tasks = modify_callback(tasks)
            if modified_tasks is not None:
                conn = None
                try:
                    conn = sqlite3.connect(self.filepath)
                    conn.execute("BEGIN TRANSACTION")
                    
                    new_tasks_map = {t["id"]: t for t in modified_tasks}
                    
                    # Delete removed tasks
                    for old_id in old_tasks_map:
                        if old_id not in new_tasks_map:
                            conn.execute("DELETE FROM tasks WHERE id = ?", (old_id,))
                            
                    # Insert new tasks and update modified ones
                    for t in modified_tasks:
                        new_id = t["id"]
                        if new_id not in old_tasks_map:
                            conn.execute(
                                "INSERT INTO tasks (id, text, completed, priority, sort_order) VALUES (?, ?, ?, ?, ?)",
                                (new_id, t["text"], 1 if t["completed"] else 0, t["priority"], t.get("sort_order", new_id * 10))
                            )
                        else:
                            old_task = old_tasks_map[new_id]
                            if (old_task["text"] != t["text"] or 
                                old_task["completed"] != t["completed"] or 
                                old_task["priority"] != t["priority"] or 
                                old_task["sort_order"] != t.get("sort_order", new_id * 10)):
                                conn.execute(
                                    "UPDATE tasks SET text = ?, completed = ?, priority = ?, sort_order = ? WHERE id = ?",
                                    (t["text"], 1 if t["completed"] else 0, t["priority"], t.get("sort_order", new_id * 10), new_id)
                                )
                                
                    conn.commit()
                    return True
                except Exception as e:
                    print(f"[TaskManager] Error updating tasks in SQLite: {e}")
                    if conn:
                        try:
                            conn.rollback()
                        except sqlite3.Error as re:
                            print(f"[TaskManager] Error rolling back: {re}")
                    return False
                finally:
                    if conn:
                        conn.close()
            return False
