import os
import sys
import time

import psycopg2
from dotenv import load_dotenv
from supabase import Client, create_client

from ledgers import sync_ledgers


def setup_db():
    load_dotenv()
    with open("trades.sql") as f:
        body_sql = f.read()

    ddl = f"""CREATE OR REPLACE FUNCTION sync_trades()
RETURNS void
LANGUAGE sql
AS $$
{body_sql}
$$;
"""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.close()
    print("setup_db complete: sync_trades() function created")


def run_pipeline():
    load_dotenv()
    supabase: Client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

    print("[1/2] Syncing ledgers from Kraken...")
    t0 = time.time()
    sync_ledgers(supabase, os.environ["PUBLIC_KEY"], os.environ["PRIVATE_KEY"])
    print(f"      Done ({time.time() - t0:.1f}s)")

    print("[2/2] Reconstructing trades from ledger pairs...")
    t0 = time.time()
    supabase.rpc("sync_trades").execute()
    print(f"      Done ({time.time() - t0:.1f}s)")

    print("Pipeline complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--setup":
        setup_db()
    else:
        run_pipeline()
