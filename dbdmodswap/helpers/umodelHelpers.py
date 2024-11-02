from .consoleHelpers import sprint
from .processHelpers import runCommand

UmodelProgramStem = 'umodel'
UmodelProgramFilename = f'{UmodelProgramStem}.exe'
UmodelSaveFolderName = 'UmodelSaved'

def runUmodelCommand(umodelPath, args, cwd=None, debug=False):
    if debug:
        allArgs = [umodelPath, *args]
        quoted = [f'"{arg}"' for arg in allArgs]
        sprint(f'cd "{cwd or "."}"')
        sprint(f"& {' '.join(quoted)}")

    for value in runCommand(umodelPath, args, cwd=cwd):
        yield value
