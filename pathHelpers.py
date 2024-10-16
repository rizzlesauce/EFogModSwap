import os
import pathlib

from consoleHelpers import sprintP, sprintPad


def normPath(path):
    if isinstance(path, str) and not path.strip():
        return ''

    if not isinstance(path, pathlib.Path):
        path = pathlib.Path(path)

    return path.as_posix()


def getPathInfo(path, relativeDir='./', debug=False):
    result = {
        'path': path,
        'normalized': '',
        'relativeDir': '',
        'relativeDirResolved': '',
        'isAbsolute': False,
        'absolute': '',
        'relative': None,
        'dir': '',
        'basename': '',
        'stem': '',
        'suffix': '',
        'suffixLower': '',
        'best': '',
    }

    if path.strip():
        result['normalized'] = normPath(path)
        relativeDirResolved = normPath(pathlib.Path(relativeDir).resolve())
        result['relativeDirResolved'] = relativeDirResolved

        if os.path.isabs(path):
            result['isAbsolute'] = True
            result['absolute'] = normPath(pathlib.Path(path).resolve())
            commonPath = normPath(os.path.commonpath([result['absolute'], relativeDirResolved]))
            if commonPath == relativeDirResolved:
                result['relative'] = normPath(os.path.relpath(result['absolute'], relativeDirResolved))
        else:
            result['absolute'] = normPath(pathlib.Path(os.path.join(relativeDir, path)).resolve())
            result['relative'] = normPath(os.path.relpath(result['absolute'], relativeDirResolved))

        pathlibPath = pathlib.Path(result['absolute'])

        result['dir'] = os.path.dirname(result['absolute'])
        if result['relative'] is not None:
            result['relativeDir'] = os.path.dirname(result['relative'])
        result['basename'] = os.path.basename(result['absolute'])
        result['stem'] = pathlibPath.stem
        result['suffix'] = pathlibPath.suffix
        result['suffixLower'] = result['suffix'].lower()
        result['best'] = result['absolute'] if result['relative'] is None else result['relative']

    if debug:
        sprintPad()
        sprintP(result)
        sprintPad()

    return result
