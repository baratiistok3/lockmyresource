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


class TableFormatter(abc.ABC):
    @abc.abstractmethod
    def to_string(self, rows) -> str:
        pass


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


class Const:
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
            cursor = self.execute_sql(
                f"SELECT user FROM {Const.LOCKS_TABLE} WHERE resource = ?;", (resource.name, ))
            row = cursor.fetchone()
            if row is None:
                self.execute_sql(
                    f"INSERT INTO {Const.LOCKS_TABLE} VALUES (?, ?, ?, ?);",
                    (resource.name, user.login, timestamp, comment, )
                )
            else:
                locking_user = row["user"]
                if locking_user is not None:
                    logging.debug(
                        f"Resource {resource.name} is already locked by {locking_user}")
                    return False

                cursor = self.execute_sql(
                    f"UPDATE {Const.LOCKS_TABLE} SET user=?, locked_at=?, comment=? WHERE resource=? AND user IS NULL;",
                    (user.login, timestamp, comment, resource.name, )
                )

            self.connection.commit()
            return True

    def release(self, resource: Resource, user: User):
        with self.connection:
            cursor = self.execute_sql(
                f"SELECT user FROM {Const.LOCKS_TABLE} WHERE resource = ?;", (resource.name, ))
            row = cursor.fetchone()
            locking_user = row["user"] if row is not None else None
            if locking_user != user.login:
                logging.debug(
                    f"Resource {resource.name} is locked by {locking_user}, not {user}")
                return False

            cursor = self.execute_sql(
                f"UPDATE {Const.LOCKS_TABLE} SET user=NULL, locked_at=NULL, comment=NULL WHERE resource=? AND user=?;",
                (resource.name, user.login, )
            )
            self.connection.commit()
            return True

    def list(self):
        with self.connection:
            cursor = self.execute_sql(
                f"SELECT resource, user, locked_at, comment FROM {Const.LOCKS_TABLE};")
            many = cursor.fetchall()
            return many


class Core:
    def __init__(self, user: User, db: Database, table_formatter: TableFormatter):
        assert user is not no_user
        self.user = user
        self.db = db
        self.table_formatter = table_formatter

    def __repr__(self):
        return f"Core[{self.user, self.db}]"

    @traced
    def list(self) -> str:
        return self.table_formatter.to_string(self.db.list())

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
