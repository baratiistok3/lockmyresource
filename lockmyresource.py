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


def traced(func):
    def inner(*args, **kwargs):
        logging.debug(f"{func.__name__}({args}, {kwargs})")
        result = func(*args, **kwargs)
        logging.debug(f"{func.__name__} returns {result}")
        return result
    return inner


class WrongDbVersionError(Exception):
    def __init__(self, program_version: str, db_version: str):
        self.program_version = program_version
        self.db_version = db_version


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
    comment: str


class Const:
    OK = 0
    FAILED = 1
    LOCKS_TABLE = "locks"
    VERSION_TABLE = "version"
    DB_VERSION = "0"


class Database:
    def __init__(self, connection: sqlite3.Connection, dbfile: Path):
        self.connection = connection
        self.dbfile = dbfile
        self.connection.row_factory = sqlite3.Row
        self.ensure_tables()

    def __repr__(self):
        return f"Database[{self.dbfile}]"

    @traced
    def execute_sql(self, sql, *args):
        return self.connection.execute(sql, *args)

    @traced
    def ensure_tables(self):
        db_version = self.get_db_version()
        if db_version is None:
            self.create_tables()
            return
        if db_version == Const.DB_VERSION:
            return
        raise WrongDbVersionError(Const.DB_VERSION, db_version)

    @traced
    def get_db_version(self):
        with self.connection:
            cursor = self.execute_sql(
                f"SELECT COUNT(1) AS count FROM sqlite_master WHERE type='table' AND name='{Const.VERSION_TABLE}'")
            if cursor.fetchone()["count"] == 0:
                return None
            cursor = self.execute_sql(
                f"SELECT MAX(version) AS version FROM {Const.VERSION_TABLE}")
            return cursor.fetchone()["version"]

    @traced
    def create_tables(self):
        logging.info(f"Initializing database in {self.dbfile}")
        with self.connection:
            for sql in [
                f"CREATE TABLE {Const.VERSION_TABLE} (version TEXT);",
                f"INSERT INTO {Const.VERSION_TABLE} VALUES ('{Const.DB_VERSION}');",
                f"CREATE TABLE {Const.LOCKS_TABLE} ("
                    "resource TEXT PRIMARY KEY NOT NULL, "
                    "user TEXT, "
                    "locked_at TIMESTAMP, "
                    "comment TEXT)"
            ]:
                self.execute_sql(sql)
            self.connection.commit()

    def lock(self, resource: Resource, user: User, timestamp: datetime.datetime, comment: str):
        with self.connection:
            cursor = self.execute_sql(f"SELECT user FROM {Const.LOCKS_TABLE} WHERE resource = ?;", (resource.name, ))
            row = cursor.fetchone()
            if row is None:
                self.execute_sql(
                    f"INSERT INTO {Const.LOCKS_TABLE} VALUES (?, ?, ?, ?);",
                    (resource.name, user.login, timestamp, comment, )
                )
            else:
                locking_user = row["user"]
                if locking_user is not None:
                    logging.debug(f"Resource {resource.name} is already locked by {locking_user}")
                    return False
                
                cursor = self.execute_sql(
                    f"UPDATE {Const.LOCKS_TABLE} SET user=?, locked_at=?, comment=? WHERE resource=? AND user IS NULL;",
                    (user.login, timestamp, comment, resource.name, )
                )
            
            self.connection.commit()
            return True

    def release(self, resource: Resource, user: User):
        with self.connection:
            cursor = self.execute_sql(f"SELECT user FROM {Const.LOCKS_TABLE} WHERE resource = ?;", (resource.name, ))
            row = cursor.fetchone()
            locking_user = row["user"] if row is not None else None
            if locking_user != user.login:
                logging.debug(f"Resource {resource.name} is locked by {locking_user}, not {user}")
                return False
            
            cursor = self.execute_sql(
                f"UPDATE {Const.LOCKS_TABLE} SET user=NULL, locked_at=NULL, comment=NULL WHERE resource=? AND user=?;",
                (resource.name, user.login, )
            )
            self.connection.commit()
            return True                

    def list(self):
        with self.connection:
            cursor = self.execute_sql(f"SELECT resource, user, locked_at, comment FROM {Const.LOCKS_TABLE};")
            many = cursor.fetchall()
            return many


class Core:
    def __init__(self, user: User, db: Database):
        assert user is not no_user
        self.user = user
        self.db = db

    def __repr__(self):
        return f"Core[{self.user, self.db}]"

    @traced
    def list(self) -> List[str]:
        # TODO: should return json or csv
        def format_row(row):
            return "{resource}\t{user}\t{locked_at}\t{comment}".format(**row)
        return ["Resource\tUser\tLocked at\tComment"] + [format_row(row) for row in self.db.list()]

    @traced
    def lock(self, resource: Resource, comment: str) -> bool:
        now = datetime.datetime.now()
        has_lock = self.db.lock(resource, self.user, now, comment)
        if has_lock is False:
            logging.warning(f"Could not lock {resource} for {self.user}")
        return has_lock

    @traced
    def release(self, resource: Resource):
        return self.db.release(resource, self.user)


class Command(abc.ABC):
    @abc.abstractmethod
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        pass


class ListCommand(Command):
    def execute(self, core: Core, cmd_args: CommandArgs) -> int:
        print("\n".join(core.list()))
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
    parser_lock.add_argument("comment", type=str)

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
        comment=args.comment if hasattr(args, "comment") else None
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
    core = Core(cmd_args.user, Database(connection, cmd_args.dbfile))
    exit_code = cmd_args.command.execute(core, cmd_args)
    connection.close()
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        sys.exit(exit_code)
