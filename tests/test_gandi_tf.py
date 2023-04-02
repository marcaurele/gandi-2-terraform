"""
Test module.
"""
from gandi_tf import __version__


def test_version():
    """Test version number"""
    assert __version__ == "0.1.0"
