import abc
import sys
import sqlite3
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class CommandArgs:
    dbfile: Path
    command: callable


@dataclass
class Resource:
    name: str


class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self, cmd_args: CommandArgs) -> int:
        pass

class ListCommand(Command):
    def execute(self, cmd_args: CommandArgs) -> int:
        print("Listing stuff")


class LockCommand(Command):
    def execute(self, cmd_args: CommandArgs) -> int:
        print("Lock a resource")


class ReleaseCommand(Command):
    def execute(self, cmd_args: CommandArgs) -> int:
        print("Release a resource")


def parse_args(argv) -> CommandArgs:
    parser = argparse.ArgumentParser(description="Lock some resources")
    parser.add_argument("--dbfile", default=Path("lockmyresource.db"), type=Path, help="File to use as database")

    subparsers = parser.add_subparsers(help="Commands")
    parser_list = subparsers.add_parser("list", help="List resources")
    parser_list.set_defaults(command=ListCommand())
    parser_lock = subparsers.add_parser("lock", help="Lock a resource")
    parser_lock.set_defaults(command=LockCommand())
    parser_lock.add_argument("resource", type=Resource)
    parser_release = subparsers.add_parser("release", help="Release a resource")
    parser_release.set_defaults(command=ReleaseCommand)
    parser_release.add_argument("resource", type=Resource)

    args = parser.parse_args(argv)
    cmd_args = CommandArgs(
        dbfile=args.dbfile, 
        command=args.command,
        resource=args.resource)
    return cmd_args


def main(argv: List[str]):
    cmd_args = parse_args(argv)
    cmd_args.command(cmd_args)


if __name__ == "__main__":
    main(sys.argv)
