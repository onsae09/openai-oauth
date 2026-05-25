#!/usr/bin/env python3
"""Interactive CUI for managing openai-oauth API keys."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_KEY_FILE = Path("api_key.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hash_key(api_key: str) -> str:
    return f"sha256:{hashlib.sha256(api_key.encode()).hexdigest()}"


def load_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "keys": []}

    with path.open("r", encoding="utf-8") as file:
        store = json.load(file)

    if not isinstance(store, dict) or not isinstance(store.get("keys"), list):
        raise SystemExit(f"Invalid API key file: {path}")

    store.setdefault("version", 1)
    return store


def save_store(path: Path, store: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def prompt(default: str, label: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def print_header(title: str) -> None:
    print("")
    print("=" * 72)
    print(title)
    print("=" * 72)


def create_key(path: Path, name: str) -> str:
    store = load_store(path)
    api_key = f"ooa_{secrets.token_urlsafe(32)}"
    entry = {
        "id": f"key_{secrets.token_hex(6)}",
        "name": name,
        "prefix": api_key[:12],
        "hash": hash_key(api_key),
        "created_at": utc_now(),
    }
    store["keys"].append(entry)
    save_store(path, store)

    print_header("API key created")
    print(f"ID:       {entry['id']}")
    print(f"Name:     {entry['name']}")
    print(f"Key file: {path}")
    print("")
    print(api_key)
    print("")
    print("Store this key now. The full value is not saved.")
    print("")
    print("Use it like this:")
    print("curl http://127.0.0.1:10531/v1/models \\")
    print(f'  -H "Authorization: Bearer {api_key}"')
    return str(entry["id"])


def format_key_line(key: dict[str, Any]) -> str:
    status = "revoked" if key.get("revoked_at") else "active"
    return (
        f"{key.get('id', '<missing-id>')} | "
        f"{key.get('name', '<unnamed>')} | "
        f"{key.get('prefix', '<no-prefix>')} | "
        f"{status} | "
        f"created={key.get('created_at', '<unknown>')}"
    )


def list_keys(path: Path) -> list[dict[str, Any]]:
    store = load_store(path)
    keys = store.get("keys", [])
    print_header(f"API keys in {path}")
    if not keys:
        print("No API keys yet.")
        return []

    for index, key in enumerate(keys, start=1):
        print(f"{index}. {format_key_line(key)}")
    return keys


def find_key(keys: list[dict[str, Any]], needle: str) -> list[dict[str, Any]]:
    return [
        key
        for key in keys
        if needle in {key.get("id"), key.get("name"), key.get("prefix")}
    ]


def revoke_key(path: Path, needle: str, *, confirm: bool = True) -> None:
    store = load_store(path)
    keys = store.get("keys", [])
    matches = find_key(keys, needle)

    if not matches:
        raise SystemExit(f"No key matched: {needle}")
    if len(matches) > 1:
        raise SystemExit(f"Multiple keys matched: {needle}")

    key = matches[0]
    if key.get("revoked_at"):
        print(f"Already revoked: {key.get('id')}")
        return

    if confirm:
        answer = input(f"Revoke {format_key_line(key)}? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled.")
            return

    key["revoked_at"] = utc_now()
    save_store(path, store)
    print(f"Revoked API key: {key.get('id')}")


def choose_key_file() -> Path:
    value = prompt(str(DEFAULT_KEY_FILE), "Key store file")
    return Path(value)


def run_cui() -> None:
    print_header("openai-oauth API key manager")
    print("This creates local API keys for the openai-oauth /v1 endpoints.")
    print("Only SHA-256 hashes are stored; full keys are printed once.")
    key_file = choose_key_file()

    while True:
        print_header("Menu")
        print(f"Key file: {key_file}")
        print("")
        print("1. Create a new API key")
        print("2. List API keys")
        print("3. Revoke an API key")
        print("4. Change key file")
        print("5. Quit")
        choice = input("Choose an option [1-5]: ").strip()

        try:
            if choice == "1":
                name = prompt("default", "Key name")
                create_key(key_file, name)
                input("Press Enter to continue...")
            elif choice == "2":
                list_keys(key_file)
                input("Press Enter to continue...")
            elif choice == "3":
                keys = list_keys(key_file)
                if keys:
                    needle = input("Enter key id, name, or prefix to revoke: ").strip()
                    if needle:
                        revoke_key(key_file, needle)
                input("Press Enter to continue...")
            elif choice == "4":
                key_file = choose_key_file()
            elif choice == "5" or choice.lower() in {"q", "quit", "exit"}:
                print("Done.")
                return
            else:
                print("Choose 1, 2, 3, 4, or 5.")
        except SystemExit as error:
            print(error)
            input("Press Enter to continue...")


def create_key_command(args: argparse.Namespace) -> None:
    create_key(Path(args.file), args.name)


def list_keys_command(args: argparse.Namespace) -> None:
    list_keys(Path(args.file))


def revoke_key_command(args: argparse.Namespace) -> None:
    revoke_key(Path(args.file), args.key, confirm=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Manage openai-oauth API keys. Run without arguments for the "
            "interactive CUI."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    create = subparsers.add_parser("create", help="Create a new API key.")
    create.add_argument("name", nargs="?", default="default")
    create.add_argument("--file", default=str(DEFAULT_KEY_FILE))
    create.set_defaults(func=create_key_command)

    list_command = subparsers.add_parser("list", help="List API keys.")
    list_command.add_argument("--file", default=str(DEFAULT_KEY_FILE))
    list_command.set_defaults(func=list_keys_command)

    revoke = subparsers.add_parser("revoke", help="Revoke a key by id, name, or prefix.")
    revoke.add_argument("key")
    revoke.add_argument("--file", default=str(DEFAULT_KEY_FILE))
    revoke.set_defaults(func=revoke_key_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        run_cui()
        return

    args.func(args)


if __name__ == "__main__":
    main()
