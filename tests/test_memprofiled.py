from unittest import TestCase
from unittest.mock import patch
import util


class ProfileMock:
    def __init__(self):
        self.results = []

    def profile(self, func):
        def inner(*args, **kwargs):
            result = func(*args, **kwargs)
            self.results.append(result)
            return result
        return inner


profile_mock_state = ProfileMock()
profile_mock = profile_mock_state.profile


def dummy_decorator(func):
    return func


class MemprofiledTestCase(TestCase):
    @patch("util.memprofiled", profile_mock)
    def test_with_profiler(self):
        @util.memprofiled
        def call_target(a: int, b: int) -> int:
            return a + b

        self.assertEqual(5, call_target(2, 3))
        self.assertEqual([5], profile_mock_state.results)
