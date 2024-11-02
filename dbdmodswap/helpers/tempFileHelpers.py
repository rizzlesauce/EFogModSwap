import pathlib
import tempfile
from contextlib import contextmanager


@contextmanager
def openTemporaryFile(dir=None, prefix=None, suffix=None, mode=None, encoding=None, deleteFirst=False):
    file = tempfile.NamedTemporaryFile(
        mode or 'w',
        dir=dir,
        prefix=prefix,
        suffix=suffix,
        encoding=encoding or 'utf-8',
        delete=False,
    )
    try:
        if deleteFirst:
            file.close()
            pathlib.Path.unlink(file.name)

        yield file
    finally:
        file.close()
        pathlib.Path.unlink(file.name, missing_ok=True)
