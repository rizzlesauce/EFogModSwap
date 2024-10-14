import pathlib
import tempfile
from contextlib import contextmanager


@contextmanager
def openTemporaryFile(dir=None, prefix=None, suffix=None, mode=None):
    file = tempfile.NamedTemporaryFile(
        dir=dir,
        prefix=prefix,
        suffix=suffix,
        mode=mode,
        delete=False,
    )
    try:
        yield file
    finally:
        file.close()
        pathlib.Path.unlink(file.name)
