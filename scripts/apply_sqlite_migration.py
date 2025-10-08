import sqlite3

fn = 'app.db'
conn = sqlite3.connect(fn)
cur = conn.cursor()
cols = [r[1] for r in cur.execute('PRAGMA table_info(users);').fetchall()]
if 'member_id' not in cols:
    cur.execute('ALTER TABLE users ADD COLUMN member_id VARCHAR(32);')
    print('added member_id')
else:
    print('member_id exists')
if 'person_id' not in cols:
    cur.execute('ALTER TABLE users ADD COLUMN person_id VARCHAR(64);')
    print('added person_id')
else:
    print('person_id exists')
conn.commit()
conn.close()
