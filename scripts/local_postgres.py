"""Optional isolated development PostgreSQL. Never used by the grader.

Uses the installed PostgreSQL binaries, a loopback-only port and private .local files.
Does not alter any existing PostgreSQL service. Run with the project virtualenv.
"""

import argparse
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres-data"
PORT = 55433


def binary(name):
    if path := shutil.which(name):
        return path
    candidate = Path(r"C:\Program Files\PostgreSQL\17\bin") / f"{name}.exe"
    if candidate.exists():
        return str(candidate)
    raise SystemExit("Install PostgreSQL or put its bin folder on PATH.")


def run(name, *args, check=True):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    # A background postmaster can inherit a pipe handle on Windows. A temporary
    # file avoids communicate() waiting forever for that inherited pipe to close.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        result = subprocess.run(
            [binary(name), *map(str, args)],
            check=False,
            creationflags=flags,
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output.seek(0)
        result.stdout = output.read()
    if check and result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"], nargs="?", default="start")
    args = parser.parse_args()
    if args.action != "start":
        result = run("pg_ctl", "-D", DATA, args.action, check=False)
        print(result.stdout)
        return
    LOCAL.mkdir(exist_ok=True)
    credentials = LOCAL / "postgres-credentials.json"
    if credentials.exists():
        values = json.loads(credentials.read_text())
    else:
        values = {"admin": secrets.token_urlsafe(32), "app": secrets.token_urlsafe(32)}
        credentials.write_text(json.dumps(values), encoding="utf-8")
    if not (DATA / "PG_VERSION").exists():
        password_file = LOCAL / "init-password"
        password_file.write_text(values["admin"], encoding="utf-8")
        try:
            result = run(
                "initdb",
                "-D",
                DATA,
                "-U",
                "dealerdesk_admin",
                "--auth=scram-sha-256",
                "--pwfile",
                password_file,
                "--encoding=UTF8",
                "--locale=C",
            )
        finally:
            password_file.unlink(missing_ok=True)
        with (DATA / "postgresql.conf").open("a", encoding="utf-8") as config:
            config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\n")
    if run("pg_ctl", "-D", DATA, "status", check=False).returncode != 0:
        run("pg_ctl", "-D", DATA, "-l", LOCAL / "postgres.log", "-w", "start")
    import psycopg
    from psycopg import sql

    with psycopg.connect(
        host="127.0.0.1",
        port=PORT,
        dbname="postgres",
        user="dealerdesk_admin",
        password=values["admin"],
        autocommit=True,
    ) as conn:
        if not conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", ("dealerdesk_app",)
        ).fetchone():
            conn.execute(
                sql.SQL("CREATE ROLE dealerdesk_app LOGIN CREATEDB PASSWORD {}").format(
                    sql.Literal(values["app"])
                )
            )
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", ("dealerdesk_dev",)
        ).fetchone():
            conn.execute("CREATE DATABASE dealerdesk_dev OWNER dealerdesk_app")
    env = ROOT / ".env"
    if not env.exists():
        env.write_text(
            f"DATABASE_URL=postgresql://dealerdesk_app:{quote(values['app'], safe='')}@127.0.0.1:{PORT}/dealerdesk_dev\n"
            "SUPPLIER_API_URL=http://127.0.0.1:8099\nSUPPLIER_API_KEY=dev-supplier-key\n"
            "GROQ_API_KEY=\nLLM_PROVIDER=groq\nLLM_MODEL=openai/gpt-oss-120b\n"
            f"DJANGO_DEBUG=1\nDJANGO_SECRET_KEY={secrets.token_urlsafe(48)}\n",
            encoding="utf-8",
        )
    print(
        f"Isolated PostgreSQL ready at 127.0.0.1:{PORT}; private .env preserved/created. No credentials printed."
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stdout)
        raise SystemExit(exc.returncode)
