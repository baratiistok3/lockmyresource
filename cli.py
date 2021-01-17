#!/usr/bin/env python3


import abc
import datetime
import logging
import os
import sys
import sqlite3
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from lockmyresource import Core, Resource, User, no_user, Database
from tableformatter import TableFormatter


class Const:
    OK = 0
    FAILED = 1


@dataclass
class CommandArgs:
    dbfile: Path
    command: "Command"
    resource: Resource
    user: User
    debug: bool
    comment: str
    table_formatter: TableFormatter


class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        pass


class ListCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        print(core.list())
        return Const.OK


class LockCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        if core.lock(cmd_args.resource, cmd_args.comment):
            print(f"Obtained lock for {cmd_args.resource}")
            return Const.OK
        print(f"SORRY, could not lock {cmd_args.resource}!")
        return Const.FAILED


class ReleaseCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        if core.release(cmd_args.resource):
            print(f"Released lock for {cmd_args.resource}")
            return Const.OK
        print(f"SORRY, could not release {cmd_args.resource}!")
        return Const.FAILED


def parse_args(argv: Optional[List[str]]) -> CommandArgs:
    parser = argparse.ArgumentParser(description="Lock some resources")
    parser.add_argument(
        "--dbfile",
        default=Path("lockmyresource.db"),
        type=Path,
        help="File to use as database",
    )
    parser.add_argument(
        "--user", default=get_current_user(), type=User, help=argparse.SUPPRESS
    )
    parser.add_argument("--debug", action="store_true")

    subparsers = parser.add_subparsers(help="Commands", required=True, dest="command")
    parser_list = subparsers.add_parser("list", help="List resources")
    parser_list.add_argument(
        "--format",
        type=str,
        default=TableFormatter.TEXT,
        choices=[TableFormatter.TEXT, TableFormatter.CSV, TableFormatter.FORMAT_JSON],
    )
    parser_list.set_defaults(command=ListCommand())

    parser_lock = subparsers.add_parser("lock", help="Lock a resource")
    parser_lock.set_defaults(command=LockCommand())
    parser_lock.add_argument("resource", type=Resource)
    parser_lock.add_argument("comment", type=str)

    parser_release = subparsers.add_parser("release", help="Release a resource")
    parser_release.set_defaults(command=ReleaseCommand())
    parser_release.add_argument("resource", type=Resource)

    args = parser.parse_args() if argv is None else parser.parse_args(argv)
    cmd_args = CommandArgs(
        debug=args.debug,
        dbfile=args.dbfile,
        user=args.user,
        command=args.command,
        resource=args.resource if hasattr(args, "resource") else None,
        comment=args.comment if hasattr(args, "comment") else None,
        table_formatter=TableFormatter.create(args.format)
        if hasattr(args, "format")
        else None,
    )
    return cmd_args


def get_current_user():
    try:
        return User(os.getlogin())
    except OSError:
        return no_user


def main() -> int:
    logging.basicConfig(level=logging.DEBUG)
    cmd_args = parse_args(argv=None)
    if cmd_args.debug is False:
        logging.getLogger().setLevel(logging.INFO)
    connection = sqlite3.connect(str(cmd_args.dbfile), isolation_level=None)
    core = Core(
        cmd_args.user, Database(connection, cmd_args.dbfile), cmd_args.table_formatter
    )
    exit_code = cmd_args.command.execute(core, cmd_args)
    connection.close()
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        sys.exit(exit_code)
