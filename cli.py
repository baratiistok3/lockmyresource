#!/usr/bin/env python3


import abc
import csv
import datetime
import io
import logging
import os
import sys
import sqlite3
import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from lockmyresource import TableFormatter, Core, Resource, User, no_user, Database


class Const:
    OK = 0
    FAILED = 1
    FORMAT_TEXT = "text"
    FORMAT_CSV = "csv"
    FORMAT_JSON = "json"


class TextFormatter(TableFormatter):
    def to_string(self, rows) -> str:
        columns = "resource user locked_at comment".split()
        header = {key: key.capitalize() for key in columns}
        rows.insert(0, header)

        column_lengths = {
            key: max([len(str(row[key])) for row in rows])
            for key in rows[0].keys()
        }

        def format_cell(column, value):
            template = f"{{value:{column_lengths[column]}}}"
            return template.format(value=str(value))

        def format_row(row):
            return " ".join([format_cell(key, row[key]) for key in row.keys()])

        lines = [
            format_row(row)
            for row in rows
        ]

        return "\n".join(lines)


class CsvFormatter(TableFormatter):
    def to_string(self, rows) -> str:
        def csv_column(name: str) -> str:
            return name.capitalize().replace("_", " ")
        
        columns = "resource user locked_at comment".split()

        memstr = io.StringIO("")
        writer = csv.DictWriter(memstr, [csv_column(column) for column in columns])
        writer.writeheader()
        for row in rows:
            writer.writerow({csv_column(column): row[column] for column in columns})

        return memstr.getvalue()


class JsonFormatter(TableFormatter):
    def to_string(self, rows) -> str:
        raise NotImplementedError()


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
    parser.add_argument("--dbfile", default=Path("lockmyresource.db"),
                        type=Path, help="File to use as database")
    parser.add_argument("--user", default=get_current_user(),
                        type=User, help=argparse.SUPPRESS)
    parser.add_argument("--debug", action="store_true")

    subparsers = parser.add_subparsers(help="Commands")
    parser_list = subparsers.add_parser("list", help="List resources")
    parser_list.add_argument("--format", type=str, default=Const.FORMAT_TEXT,
                             choices=[Const.FORMAT_TEXT, Const.FORMAT_CSV, Const.FORMAT_JSON])
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
        comment=args.comment if hasattr(args, "comment") else None,
        table_formatter=make_formatter(args.format) if hasattr(args, "format") else None,
    )
    return cmd_args


def make_formatter(format: str):
    if format == Const.FORMAT_TEXT:
        return TextFormatter()
    if format == Const.FORMAT_CSV:
        return CsvFormatter()
    if format == Const.FORMAT_JSON:
        return JsonFormatter()


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
    core = Core(cmd_args.user, Database(
        connection, cmd_args.dbfile), cmd_args.table_formatter)
    exit_code = cmd_args.command.execute(core, cmd_args)
    connection.close()
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        sys.exit(exit_code)
