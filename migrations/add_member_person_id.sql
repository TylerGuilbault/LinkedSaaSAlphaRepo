-- migration to add member_id and person_id columns to users table
-- For SQLite, ALTER TABLE only supports adding columns; this adds nullable columns.

ALTER TABLE users ADD COLUMN member_id VARCHAR(32);
ALTER TABLE users ADD COLUMN person_id VARCHAR(64);

-- For other DBs (Postgres/MySQL), adapt types as needed:
-- ALTER TABLE users ADD COLUMN member_id VARCHAR(32);
-- ALTER TABLE users ADD COLUMN person_id VARCHAR(64);
