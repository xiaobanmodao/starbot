import { createRequire } from 'module';
import { tool } from './registry.js';

tool('sqlite_query', 'Execute a SQL query on a SQLite database file. Returns results as JSON.', {
  properties: {
    db_path: { type: 'string', description: 'Path to SQLite database file' },
    sql: { type: 'string', description: 'SQL query to execute' },
  },
  required: ['db_path', 'sql'],
}, true, ({ db_path, sql }) => {
  try {
    const require = createRequire(import.meta.url);
    const Database = require('better-sqlite3');
    const db = new Database(db_path);
    const trimmed = sql.trim().toUpperCase();
    if (trimmed.startsWith('SELECT') || trimmed.startsWith('PRAGMA')) {
      const rows = db.prepare(sql).all().slice(0, 200);
      db.close();
      return JSON.stringify(rows, null, 2);
    }
    const info = db.prepare(sql).run();
    db.close();
    return `OK, ${info.changes} rows affected`;
  } catch (e) {
    return `[error] ${e.message}`;
  }
});
