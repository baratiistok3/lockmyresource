import sys
from pathlib import Path
"""Top-level package for Lock My Resource."""

__author__ = """Szabó Péter"""
__email__ = '1254135+szabopeter@users.noreply.github.com'
__version__ = '0.2.0'

lockmyresource_path = Path(__file__).parent
assert isinstance(lockmyresource_path, Path)
sys.path.insert(0, str(lockmyresource_path.absolute()))
