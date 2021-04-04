import os
import logging
from tempfile import TemporaryDirectory
from unittest import TestCase
# This is needed for the next line to work in the integration test execution context
try:
    from lockmyresource import *
except ImportError:
    pass
from core import Core, Database, User, Resource
from tableformatter import TextFormatter


logging.basicConfig(level=logging.DEBUG)


class LockMyResourceIntegration(TestCase):
    def test_basic_session(self):
        with TemporaryDirectory() as tempdir:
            db = Database.open(os.path.join(tempdir, "lockmyresource.db"))
            fork = Resource("fork1")
            locke_session = Core(User("Locke"), db, TextFormatter())
            descartes_session = Core(User("Descartes"), db, TextFormatter())
            self.assertTrue(locke_session.lock(fork, "Never mind"))
            self.assertFalse(descartes_session.lock(fork, "In your dreams"))
            locks = locke_session.list()
            self.assertEqual(1, len(locks), str(locks))
            lock = locks[0]
            self.assertEqual("fork1", lock.resource.name)
            self.assertEqual("Locke", lock.user.login)
            self.assertFalse(descartes_session.release(fork))
            self.assertTrue(locke_session.release(fork))
