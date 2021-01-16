#!/usr/bin/env python3


import abc
import logging
import os
import sys
import sqlite3
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def traced(func):
    def inner(*args, **kwargs):
        logging.debug(f"{func.__name__}({args}, {kwargs})")
        result = func(*args, **kwargs)
        logging.debug(f"{func.__name__} returns {result}")
        return result
    return inner


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
    debug: bool


class Database:
    def __init__(self, dbfile: Path):
        self.dbfile = dbfile
        if dbfile.exists() is False:
            self.create_db()

    def __repr__(self):
        return f"Database[{self.dbfile}]"
    
    def create_db(self):
        logging.info(f"Creating database {self.dbfile}")
        pass


class Core:
    def __init__(self, user: User, db: Database):
        assert user is not no_user
        self.user = user
        self.db = db

    def __repr__(self):
        return f"Core[{self.user, self.db}]"

    @traced
    def list(self) -> List[str]:
        return ["Place for the list"]
    
    @traced
    def lock(self, resource: Resource):
        print(f"TODO lock {resource} for {self.user}")
    
    @traced
    def release(self, resource: Resource):
        print(f"TODO release {resource} from {self.user}")


class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        pass


class ListCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        print("\n".join(core.list()))


class LockCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        core.lock(cmd_args.resource)


class ReleaseCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        core.release(cmd_args.resource)


def parse_args(argv: Optional[List[str]]) -> CommandArgs:
    parser = argparse.ArgumentParser(description="Lock some resources")
    parser.add_argument("--dbfile", default=Path("lockmyresource.db"),
                        type=Path, help="File to use as database")
    parser.add_argument("--user", default=get_current_user(),
                        type=User, help=argparse.SUPPRESS)
    parser.add_argument("--debug", action="store_true")

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
        debug=args.debug,
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
    logging.basicConfig(level=logging.DEBUG)
    cmd_args = parse_args(argv=None)
    if cmd_args.debug is False:
        logging.getLogger().setLevel(logging.INFO)
    core = Core(cmd_args.user, Database(cmd_args.dbfile))
    cmd_args.command.execute(core, cmd_args)


if __name__ == "__main__":
    main(sys.argv)
