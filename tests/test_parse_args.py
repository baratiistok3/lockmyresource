from unittest import TestCase
from pathlib import Path

from cli import parse_args, ListCommand, LockCommand, ReleaseCommand
from configfile import LockMyResourceConfig


config = LockMyResourceConfig("dummy", ":memory:", "dummy")


class ParseTestCase(TestCase):
    def test_dbfile(self):
        cmd_args = parse_args("--dbfile mydbfile.sqlite list".split(), config)
        self.assertEqual(Path("mydbfile.sqlite"), cmd_args.dbfile)
        self.assertIsInstance(cmd_args.command, ListCommand)
        self.assertIsNone(cmd_args.resource)

    def test_lock_and_release(self):
        for expected_command_type, command in [
            (LockCommand, ["lock", "some-resource", "comment"]),
            (ReleaseCommand, ["release", "some-resource"]),
        ]:
            with self.subTest(command):
                cmd_args = parse_args(command, config)
                self.assertEqual(config.dbfile, str(cmd_args.dbfile))
                self.assertIsInstance(cmd_args.command, expected_command_type)
                self.assertEqual("some-resource", cmd_args.resource.name)
