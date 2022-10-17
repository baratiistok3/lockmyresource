import unittest

from core import User, no_user


class UserTestCase(unittest.TestCase):
    def test_equality(self):
        self.assertEqual(User(None), User(None))

    def test_same(self):
        self.assertEqual(no_user, User(None))
        self.assertIsNot(User(None), no_user)
