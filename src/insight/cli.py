"""CLI for managing API keys.

Usage:
    python -m insight.cli create  "my-agent"
    python -m insight.cli list
    python -m insight.cli revoke  "my-agent"
"""
from __future__ import annotations

import argparse
import sys

from .keystore import KeyStore


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="insight-keys",
        description="Manage Insight Engine API keys.",
    )
    parser.add_argument(
        "--keys-file",
        default="keys.csv",
        help="Path to the keys CSV file (default: keys.csv)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a new API key")
    p_create.add_argument("name", help="A label for this key (e.g. 'my-agent', 'dev-test')")

    # list
    sub.add_parser("list", help="List all API keys")

    # revoke
    p_revoke = sub.add_parser("revoke", help="Revoke a key by name")
    p_revoke.add_argument("name", help="Name of the key to revoke")

    args = parser.parse_args()
    ks = KeyStore(args.keys_file)

    if args.command == "create":
        record = ks.create_key(args.name)
        print(f"\nAPI key created successfully!\n")
        print(f"  Name:  {record['name']}")
        print(f"  Key:   {record['key']}")
        print(f"\n  Save this key — it won't be shown again.\n")
        print(f"  Usage:")
        print(f"    curl -H 'Authorization: Bearer {record['key']}' \\")
        print(f"         -H 'Content-Type: application/json' \\")
        print(f"         -d '{{\"type\":\"search\",\"query\":\"test\"}}' \\")
        print(f"         http://127.0.0.1:8000/insight")

    elif args.command == "list":
        keys = ks.list_keys()
        if not keys:
            print("No keys found.")
            return
        print(f"\n{'Name':<20} {'Key':<25} {'Created':<28} {'Active'}")
        print("-" * 80)
        for k in keys:
            print(f"{k['name']:<20} {k['key']:<25} {k['created_at']:<28} {k['active']}")
        print()

    elif args.command == "revoke":
        if ks.revoke_key(args.name):
            print(f"Revoked all keys named '{args.name}'.")
        else:
            print(f"No active key found with name '{args.name}'.")
            sys.exit(1)


if __name__ == "__main__":
    main()
