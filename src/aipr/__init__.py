"""aipr: read an open-source repository's AI contribution policy."""

from importlib.metadata import PackageNotFoundError, version as _metadata_version

try:
    __version__ = _metadata_version("aipr-py")
except PackageNotFoundError:  # running from a source checkout, not an install
    __version__ = "0.0.0.dev0"