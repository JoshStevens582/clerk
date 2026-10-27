"""One-off: Resend rejects @example.com recipients. Run against production DB if needed."""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "/app/data/clerk.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute(
    """
    UPDATE inbound_messages
    SET from_email = REPLACE(from_email, '@example.com', '@customchatandautomation.co.za')
    WHERE from_email LIKE '%@example.com'
    """
)
cur.execute(
    """
    UPDATE inbound_messages
    SET from_email = 'demo+frontdesk@customchatandautomation.co.za'
    WHERE from_email LIKE '%capephysio%'
    """
)
conn.commit()
for row in cur.execute("SELECT id, from_email FROM inbound_messages"):
    print(row)
conn.close()
