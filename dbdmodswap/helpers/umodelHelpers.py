import os

from dbdmodswap.metadata.programMetaData import ProgramName

from .consoleHelpers import sprint, sprintP, sprintPad
from .pathHelpers import getPathInfo, normPath
from .processHelpers import runCall
from .tempFileHelpers import openTemporaryFile

UmodelProgramStem = 'umodel'
UmodelProgramFilename = f'{UmodelProgramStem}.exe'

def umodelExport(pakPath, destDir, gameName, unrealPakPath):
    # TODO: get this working using umodel
    pakPathInfo = getPathInfo(pakPath)
    programPathInfo = getPathInfo(unrealPakPath)
    programFilename = programPathInfo['basename']
    programPath = normPath(os.path.join(programPathInfo['dir'], programFilename))
    destDirPathInfo = getPathInfo(destDir)
    actualDestDir = ''
    if not os.path.exists(actualDestDir):
        os.makedirs(actualDestDir, exist_ok=True)
    args = [
        programPath,
        pakPathInfo['absolute'],
        '-extract',
        actualDestDir,
        # TODO: remove - doesn't seem to be needed
        #'-extracttomountpoint',
    ]
    runCall(args, cwd=programPathInfo['dir'])
