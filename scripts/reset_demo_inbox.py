"""Put demo inbox rows back on the list (clear task_id). Safe to re-run Clerk on them."""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/clerk.db"
conn = sqlite3.connect(db_path)
conn.execute("UPDATE inbound_messages SET task_id = NULL")
conn.commit()
for row in conn.execute("SELECT id, subject, task_id FROM inbound_messages ORDER BY id"):
    print(row)
conn.close()
