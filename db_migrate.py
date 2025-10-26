import sqlite3, os, sys
DB="briefs.db"
con=sqlite3.connect(DB)
cur=con.cursor()

# facts: append-only notes from /update (and later: auto-extracted)
cur.execute("""
CREATE TABLE IF NOT EXISTS facts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_utc TEXT NOT NULL,
  author_slack_id TEXT NOT NULL,
  text TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',  -- manual|dm|call
  confidence TEXT NOT NULL DEFAULT 'high' -- high|medium|low
);
""")

# calls: to mark last call time (used by /callprep)
cur.execute("""
CREATE TABLE IF NOT EXISTS calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_utc TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'manual',  -- manual|transcript
  notes TEXT
);
""")

con.commit(); con.close()
print("✅ DB migration complete.")
