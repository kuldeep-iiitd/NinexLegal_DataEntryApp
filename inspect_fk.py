import sqlite3
conn=sqlite3.connect('db.sqlite3')
cur=conn.cursor()
print('Schema for cases_case:')
row=cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cases_case'").fetchone()
print(row[0] if row else 'NOT FOUND')
print('\nForeign keys for cases_case:')
for fk in cur.execute("PRAGMA foreign_key_list('cases_case')").fetchall():
    print(fk)
print('\nBank table names:')
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%bank%' ").fetchall():
    print(r[0])

print('\nSchema for legacy cases_bank:')
row=cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cases_bank'").fetchone()
print(row[0] if row else 'NOT FOUND')
print('\nSchema for legacy cases_branch:')
row=cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='cases_branch'").fetchone()
print(row[0] if row else 'NOT FOUND')
