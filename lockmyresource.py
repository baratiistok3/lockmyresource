import datetime
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from tableformatter import TableFormatter, rows_to_dicts


def traced(func):
    def inner(*args, **kwargs):
        logging.debug("%s(%s, %s)", func.__name__, args, kwargs)
        result = func(*args, **kwargs)
        logging.debug("{%s} returns {%s}", func.__name__, result)
        return result

    return inner


class WrongDbVersionError(Exception):
    def __init__(self, program_version: str, db_version: str):
        self.program_version = program_version
        self.db_version = db_version
        super().__init__(
            f"Program ({program_version}) and DB version ({db_version}) don't match!",
        )


class InvalidUserError(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@dataclass
class Resource:
    name: str


@dataclass
class User:
    login: str
    @staticmethod
    def from_os() -> "User":
        try:
            return User(os.getlogin())
        except OSError:
            return no_user


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

    @staticmethod
    @traced
    def open(dbfile: Path):
        connection = sqlite3.connect(str(dbfile), isolation_level=None)
        return Database(connection, dbfile)

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
                f"SELECT COUNT(1) AS count FROM sqlite_master "
                f"WHERE type='table' AND name='{Const.VERSION_TABLE}'"
            )
            if cursor.fetchone()["count"] == 0:
                return None
            cursor = self.execute_sql(
                f"SELECT MAX(version) AS version FROM {Const.VERSION_TABLE}"
            )
            return cursor.fetchone()["version"]

    @traced
    def create_tables(self):
        logging.info("Initializing database in {%s}", self.dbfile)
        with self.connection:
            for sql in [
                f"CREATE TABLE {Const.VERSION_TABLE} (version TEXT);",
                f"INSERT INTO {Const.VERSION_TABLE} VALUES ('{Const.DB_VERSION}');",
                f"CREATE TABLE {Const.LOCKS_TABLE} ("
                "resource TEXT PRIMARY KEY NOT NULL, "
                "user TEXT, "
                "locked_at TIMESTAMP, "
                "comment TEXT)",
            ]:
                self.execute_sql(sql)
            self.connection.commit()

    def lock(
        self, resource: Resource, user: User, timestamp: datetime.datetime, comment: str
    ):
        with self.connection:
            cursor = self.execute_sql(
                f"SELECT user FROM {Const.LOCKS_TABLE} WHERE resource = ?;",
                (resource.name,),
            )
            row = cursor.fetchone()
            if row is None:
                self.execute_sql(
                    f"INSERT INTO {Const.LOCKS_TABLE} VALUES (?, ?, ?, ?);",
                    (
                        resource.name,
                        user.login,
                        timestamp,
                        comment,
                    ),
                )
            else:
                locking_user = row["user"]
                if locking_user is not None:
                    logging.debug(
                        "Resource {%s} is already locked by {%s}",
                        resource.name,
                        locking_user,
                    )
                    return False

                cursor = self.execute_sql(
                    f"UPDATE {Const.LOCKS_TABLE} SET user=?, locked_at=?, comment=? "
                    f"WHERE resource=? AND user IS NULL;",
                    (
                        user.login,
                        timestamp,
                        comment,
                        resource.name,
                    ),
                )

            self.connection.commit()
            return True

    def release(self, resource: Resource, user: User) -> bool:
        with self.connection:
            cursor = self.execute_sql(
                f"SELECT user FROM {Const.LOCKS_TABLE} WHERE resource = ?;",
                (resource.name,),
            )
            row = cursor.fetchone()
            locking_user = row["user"] if row is not None else None
            if locking_user != user.login:
                logging.debug(
                    "Resource {resource.name} is locked by {%s}, not {%s}",
                    locking_user,
                    user,
                )
                return False

            cursor = self.execute_sql(
                f"UPDATE {Const.LOCKS_TABLE} SET user=NULL, locked_at=NULL, comment=NULL "
                f"WHERE resource=? AND user=?;",
                (
                    resource.name,
                    user.login,
                ),
            )
            self.connection.commit()
            return True

    def list(self):
        with self.connection:
            cursor = self.execute_sql(
                f"SELECT resource, user, locked_at, comment FROM {Const.LOCKS_TABLE};"
            )
            many = cursor.fetchall()
            return many


class LockRecord:
    def __init__(self, core: "Core", resource: Resource, user: User, locked_at: datetime.datetime, comment: str):
        self.core = core
        self.resource = resource
        self.user = user
        self.locked_at = locked_at
        self.comment = comment

    def lock(self, comment: str) -> bool:
        return self.core.lock(self.resource, comment)

    def release(self) -> bool:
        return self.core.release(self.resource)


class Core:
    def __init__(self, user: User, database: Database, table_formatter: TableFormatter):
        if user is no_user or not isinstance(user, User) or not user.login:
            raise InvalidUserError()
        self.user = user
        self.database = database
        self.table_formatter = table_formatter

    def __repr__(self):
        return f"Core[{self.user, self.database}]"

    @traced
    def set_dbfile(self, dbfile: Path):
        self.database.connection.close()
        self.database = Database.open(dbfile)

    @traced
    def list_str(self) -> str:
        return self.table_formatter.to_string(self.database.list())
    
    @traced
    def list_raw(self) -> List[Dict]:
        return rows_to_dicts(self.database.list())

    @traced
    def list(self) -> List[LockRecord]:
        return [LockRecord(self, Resource(row["resource"]), User(row["user"]), row["locked_at"], row["comment"]) 
                for row in self.list_raw()]

    @traced
    def lock(self, resource: Resource, comment: str) -> bool:
        now = datetime.datetime.now()
        has_lock = self.database.lock(resource, self.user, now, comment)
        if has_lock is False:
            logging.warning("Could not lock {%s} for {%s}", resource, self.user)
        return has_lock

    @traced
    def release(self, resource: Resource) -> bool:
        return self.database.release(resource, self.user)
