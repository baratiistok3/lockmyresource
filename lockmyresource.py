#!/usr/bin/env python3


import abc
import os
import sys
import sqlite3
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class Resource:
    name: str


@dataclass
class User:
    login: str


no_user = User(None)


@dataclass
class CommandArgs:
    dbfile: Path
    command: "Command"
    resource: Resource
    user: User


class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self, cmd_args: CommandArgs) -> int:
        pass


class ListCommand(Command):
    def execute(self, cmd_args: CommandArgs) -> int:
        print("Listing stuff")


class LockCommand(Command):
    def execute(self, cmd_args: CommandArgs) -> int:
        print(f"TODO: lock {cmd_args.resource}")


class ReleaseCommand(Command):
    def execute(self, cmd_args: CommandArgs) -> int:
        print(f"TODO: release {cmd_args.resource}")


def parse_args(argv: Optional[List[str]]) -> CommandArgs:
    parser = argparse.ArgumentParser(description="Lock some resources")
    parser.add_argument("--dbfile", default=Path("lockmyresource.db"),
                        type=Path, help="File to use as database")
    parser.add_argument("--user", default=get_current_user(),
                        type=User, help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(help="Commands")
    parser_list = subparsers.add_parser("list", help="List resources")
    parser_list.set_defaults(command=ListCommand())

    parser_lock = subparsers.add_parser("lock", help="Lock a resource")
    parser_lock.set_defaults(command=LockCommand())
    parser_lock.add_argument("resource", type=Resource)

    parser_release = subparsers.add_parser(
        "release", help="Release a resource")
    parser_release.set_defaults(command=ReleaseCommand())
    parser_release.add_argument("resource", type=Resource)

    args = parser.parse_args() if argv is None else parser.parse_args(argv)
    cmd_args = CommandArgs(
        dbfile=args.dbfile,
        user=args.user,
        command=args.command,
        resource=args.resource if hasattr(args, "resource") else None,
    )
    return cmd_args


def get_current_user():
    try:
        return User(os.getlogin())
    except OSError:
        return no_user


def main(argv: List[str]):
    cmd_args = parse_args(argv=None)
    cmd_args.command.execute(cmd_args)


if __name__ == "__main__":
    main(sys.argv)
