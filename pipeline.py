import os
import sys
import time

import psycopg2
from dotenv import load_dotenv
from supabase import Client, create_client

from ledgers import sync_ledgers
from trades_history import sync_trades as sync_trades_history


def _create_function(cur, name: str, sql_file: str) -> None:
    with open(sql_file) as f:
        body_sql = f.read()
    ddl = f"""CREATE OR REPLACE FUNCTION {name}()
RETURNS void
LANGUAGE sql
AS $$
{body_sql}
$$;
"""
    cur.execute(ddl)
    print(f"setup_db: {name}() created")


def setup_db():
    load_dotenv()
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        _create_function(cur, "sync_trades", "sql/trades.sql")
        _create_function(cur, "sync_realized_pnl", "sql/realized_pnl.sql")
        with open("sql/bot.ddl.sql") as f:
            cur.execute(f.read())
        print("setup_db: bot tables applied (sql/bot.ddl.sql)")
    conn.close()
    print("setup_db complete")


def run_pipeline():
    load_dotenv()
    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

    print("[1/4] Syncing ledgers from Kraken...")
    t0 = time.time()
    sync_ledgers(supabase, os.environ["PUBLIC_KEY"], os.environ["PRIVATE_KEY"])
    print(f"      Done ({time.time() - t0:.1f}s)")

    print("[2/4] Syncing trades history from Kraken...")
    t0 = time.time()
    sync_trades_history(supabase, os.environ["PUBLIC_KEY"], os.environ["PRIVATE_KEY"])
    print(f"      Done ({time.time() - t0:.1f}s)")

    print("[3/4] Reconstructing trades from ledger pairs...")
    t0 = time.time()
    supabase.rpc("sync_trades").execute()
    print(f"      Done ({time.time() - t0:.1f}s)")

    print("[4/4] Computing realized P&L...")
    t0 = time.time()
    supabase.rpc("sync_realized_pnl").execute()
    print(f"      Done ({time.time() - t0:.1f}s)")

    print("Pipeline complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        setup_db()
    else:
        run_pipeline()
