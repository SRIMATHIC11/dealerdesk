"""Run the exact initialization contract in an isolated source copy and PostgreSQL DB.

Uses existing installed dependencies. It never resets the development database.
Creates temporary test records and a uniquely named database, then cleans up that DB.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
import requests
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", choices=["aiml", "django", "all"], default="all")
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}
    # Real process configuration wins over local defaults, just like Django settings.
    env.update(os.environ)
    url = env.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL privately first.")
    parsed = urlsplit(url)
    name = "dealerdesk_verify_" + uuid.uuid4().hex[:12]
    maintenance = urlunsplit(parsed._replace(path="/postgres"))
    database = urlunsplit(parsed._replace(path="/" + quote(name)))
    root_local = ROOT / ".local"
    root_local.mkdir(exist_ok=True)
    copied = Path(tempfile.mkdtemp(prefix="submission-", dir=root_local))
    subprocess.run(
        ["git", "ls-files", "--others", "--cached", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--others", "--cached", "--exclude-standard", "-z"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    for entry in files:
        if not entry or entry.startswith("system_arch/"):
            continue
        source = ROOT / entry
        if source.is_file():
            target = copied / entry
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    assert not (copied / ".env").exists(), "Secrets must not be in submission copy."
    env.update(DATABASE_URL=database, DJANGO_DEBUG="1", PYTHONUNBUFFERED="1")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    server = None
    with psycopg.connect(maintenance, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        for command in [["migrate", "--noinput"], ["seed_data"], ["seed_data"]]:
            subprocess.run([sys.executable, "manage.py", *command], cwd=copied, env=env, check=True)
        log = root_local / "submission-server.log"
        with log.open("w", encoding="utf-8") as output:
            server = subprocess.Popen(
                [sys.executable, "manage.py", "runserver", f"127.0.0.1:{args.port}", "--noreload"],
                cwd=copied,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        base = f"http://127.0.0.1:{args.port}"
        for _ in range(60):
            if server.poll() is not None:
                raise RuntimeError("Verification server exited; see .local/submission-server.log")
            try:
                if requests.get(base + "/api/health/", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("Verification server did not become ready.")
        response = requests.get(base + "/", timeout=5)
        response.raise_for_status()
        assets = re.findall(r'(?:src|href)="(/static/[^\"]+)"', response.text)
        assert len(assets) >= 2, "Expected compiled JavaScript and CSS assets."
        for asset in assets:
            requests.get(base + asset, timeout=5).raise_for_status()
        print("Clean source copy serves the UI without Node or collectstatic.")
        flags_args = ["--all"] if args.track == "all" else ["--track", args.track]
        result = subprocess.run(
            [sys.executable, "smoke_test.py", "--base-url", base, *flags_args], cwd=copied, env=env
        )
        return result.returncode
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        with psycopg.connect(maintenance, autocommit=True) as admin:
            # Only drop the unique database created by this invocation.
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        print(
            f"Isolated validation complete; source snapshot retained in {copied.relative_to(ROOT)}. Development DB preserved."
        )


if __name__ == "__main__":
    raise SystemExit(main())
