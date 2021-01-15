from unittest import TestCase
from pathlib import Path

from lockmyresource import parse_args, ListCommand, LockCommand, ReleaseCommand


class ParseTestCase(TestCase):
    def test_dbfile(self):
        cmd_args = parse_args("--dbfile mydbfile.sqlite list".split())
        self.assertEqual(Path("mydbfile.sqlite"), cmd_args.dbfile)
        self.assertIsInstance(cmd_args.command, ListCommand)
        self.assertIsNone(cmd_args.resource)

    def test_lock_and_release(self):
        for command_type, command in [
            (LockCommand, "lock"),
            (ReleaseCommand, "release"),
        ]:
            with self.subTest(command):
                cmd_args = parse_args([command, "some-resource"])
                self.assertIn(".db", str(cmd_args.dbfile))
                self.assertIsInstance(cmd_args.command, command_type)
                self.assertEqual("some-resource", cmd_args.resource.name)
