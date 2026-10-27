import sqlite3
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/clerk.db"
c = sqlite3.connect(path)
print("inbound_messages", c.execute("select id, subject, task_id from inbound_messages").fetchall())
print("pending tasks", c.execute("select id, kind, substr(inbound_text,1,60) from tasks where status='pending'").fetchall())
