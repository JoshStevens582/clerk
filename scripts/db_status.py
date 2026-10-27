import sqlite3
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/clerk.db"
conn = sqlite3.connect(path)
inbound = conn.execute(
    "SELECT id, subject, task_id FROM inbound_messages",
).fetchall()
pending = conn.execute(
    "SELECT id, kind, substr(inbound_text, 1, 60) FROM tasks WHERE status = 'pending'",
).fetchall()
print("inbound_messages", inbound)
print("pending tasks", pending)
conn.close()
