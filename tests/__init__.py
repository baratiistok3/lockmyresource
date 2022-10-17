import sys
from pathlib import Path

"""Unit test package for lockmyresource."""

lockmyresource_path = Path(__file__).parent.parent / "lockmyresource"
assert isinstance(lockmyresource_path, Path)
sys.path.insert(0, str(lockmyresource_path.absolute()))
