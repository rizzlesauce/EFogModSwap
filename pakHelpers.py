import os
import re

from pathHelpers import getPathInfo, normPath
from consoleHelpers import sprint, sprintP, sprintPad
from processHelpers import runCall
from tempFileHelpers import openTemporaryFile

DefaultPlatform = 'WindowsNoEditor'

UnrealPakProgramStem = 'UnrealPak'
UnrealPakProgramFilename = f'{UnrealPakProgramStem}.exe'
PakchunkFileExtension = '.pak'

def getPakContentDir(pakDir, gameName):
    return normPath(os.path.join(pakDir, gameName, 'Content'))


def getPakchunkFilenameRegex():
    return re.compile(r'^^pakchunk(?P<number>\d+)(?P<name>\w+)?(?P<platformPart>-(?P<platform>\w+)?)?(?P<suffix>\.pak)?$$', re.IGNORECASE)


def getPackchunkFilenameParts(filenameOrStem):
    match = getPakchunkFilenameRegex().match(filenameOrStem)
    if match:
        result = match.groupdict()
        result['number'] = int(result['number'])
        return result


def toPakchunkStem(pakNumber, pakName=None, platform=None):
    stem = f'pakchunk{pakNumber}{pakName or ""}'
    if platform:
        stem = f'{stem}-{platform}'
    return stem


def unrealPak(pakDir, destPakPath, unrealPakPath, compress=True, debug=False):
    pakDirPathInfo = getPathInfo(pakDir)
    responseFileContent = f'"{pakDirPathInfo["absolute"]}\*.*" "..\..\..\*.*" '
    if debug:
        sprintPad()
        sprint(f'Response file content: {responseFileContent}')
        sprintPad()

    programPathInfo = getPathInfo(unrealPakPath)
    programFilename = programPathInfo['basename']
    programPath = normPath(os.path.join(programPathInfo['dir'], programFilename))
    responseFilePath = None

    def runCommand(responseFile):
        if debug:
            sprintPad()
            sprint(f'Running UnrealPak')
            sprint(f'Response file content: `{responseFileContent}`')
            sprint(f'Writing response file content to "{normPath(responseFile.name)}"')
            sprintPad()

        responseFile.write(responseFileContent)
        responseFile.close()

        args = [
            programPath,
            getPathInfo(destPakPath)['absolute'],
            f'-create={normPath(responseFile.name)}',
        ]
        if compress:
            args.append('-compress')

        if debug:
            sprintPad()
            sprintP(args)
            sprintPad()

        runCall(args, cwd=programPathInfo['dir'])

    usingTempFile = True

    if usingTempFile:
        with openTemporaryFile(
            prefix='DbdSocketsMixer_UnrealPak_filelist_',
            suffix='.txt',
            mode='w',
            dir=programPathInfo['dir'],
        ) as file:
            runCommand(file)
    else:
        responseFilePath = normPath(os.path.join(programPathInfo['dir'], 'DbdSocketsMixer_UnrealPak_filelist.txt'))
        with open(responseFilePath, 'w') as file:
            runCommand(file)

    # TODO: do we need to use gamepath.txt or do anything with *.sig files?

    return responseFilePath


def unrealUnpak(pakPath, destDir, gameName, unrealPakPath):
    pakPathInfo = getPathInfo(pakPath)
    programPathInfo = getPathInfo(unrealPakPath)
    programFilename = programPathInfo['basename']
    programPath = normPath(os.path.join(programPathInfo['dir'], programFilename))
    destDirPathInfo = getPathInfo(destDir)
    actualDestDir = getPakContentDir(destDirPathInfo['absolute'], gameName)
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
