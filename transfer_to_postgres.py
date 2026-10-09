"""Copy SQLite to EMPTY PostgreSQL. Set DATABASE_URL, run --source shop.db.
Stop the shop first. Source is opened read-only; IDs and password hashes are preserved.
"""
import argparse
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, select, text, func
from config import Config
from models import db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    source_path = Path(args.source).resolve(strict=True)
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, **Config.SQLALCHEMY_ENGINE_OPTIONS)
    if engine.dialect.name != 'postgresql':
        raise SystemExit('Destination DATABASE_URL must be PostgreSQL.')
    source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
    snapshot = sqlite3.connect(':memory:')
    try:
        source.backup(snapshot)
        snapshot.row_factory = sqlite3.Row
        with engine.begin() as conn:
            conn.execute(text('SELECT pg_advisory_xact_lock(72024001)'))
            db.metadata.create_all(conn)
            tables = db.metadata.sorted_tables
            for table in tables:
                if conn.scalar(select(func.count()).select_from(table)):
                    raise RuntimeError('Destination must be empty; no rows were copied.')
            for table in tables:
                rows = snapshot.execute(f'SELECT * FROM "{table.name}"').fetchall()
                for start in range(0, len(rows), 500):
                    batch = []
                    for row in rows[start:start + 500]:
                        item = {c.name: row[c.name] for c in table.columns if c.name in row.keys()}
                        for column in table.columns:
                            if isinstance(column.type, db.Boolean) and item.get(column.name) is not None:
                                item[column.name] = bool(item[column.name])
                        batch.append(item)
                    if batch:
                        conn.execute(table.insert(), batch)
                sequence = conn.scalar(text('SELECT pg_get_serial_sequence(:table, :column)'),
                                       {'table': table.name, 'column': 'id'})
                if sequence:
                    maximum = conn.scalar(select(func.max(table.c.id)))
                    conn.execute(text('SELECT setval(CAST(:seq AS regclass), :value, :called)'),
                                 {'seq': sequence, 'value': maximum or 1, 'called': maximum is not None})
                print(f'{table.name}: {len(rows)} rows')
        print('Transfer committed. Source SQLite unchanged.')
    finally:
        source.close()
        snapshot.close()
        engine.dispose()


if __name__ == '__main__':
    main()
