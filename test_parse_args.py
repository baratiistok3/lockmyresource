from unittest import TestCase
from pathlib import Path

from lockmyresource import parse_args, ListCommand


class ParseTestCase(TestCase):
    def test_dbfile(self):
        cmd_args = parse_args("--dbfile mydbfile.sqlite list".split())
        self.assertEqual(Path("mydbfile.sqlite"), cmd_args.dbfile)
        self.assertIsInstance(cmd_args.command, ListCommand)
