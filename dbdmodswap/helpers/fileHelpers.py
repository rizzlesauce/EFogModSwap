import os

from .pathHelpers import normPath


def listFilesRecursively(dir):
    """Lists all files in a directory recursively as relative paths."""
    for root, dirs, files in os.walk(dir):
        for file in files:
            absolutePath = os.path.join(root, file)
            relativePath = os.path.relpath(absolutePath, dir)
            yield normPath(relativePath)
