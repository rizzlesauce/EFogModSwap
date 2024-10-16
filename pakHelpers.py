import os
import re

from consoleHelpers import sprint, sprintP, sprintPad
from pathHelpers import getPathInfo, normPath
from processHelpers import runCall
from programMetaData import ProgramName
from tempFileHelpers import openTemporaryFile

DefaultPlatform = 'WindowsNoEditor'

UnrealPakProgramStem = 'UnrealPak'
UnrealPakProgramFilename = f'{UnrealPakProgramStem}.exe'

PakchunkFilenamePrefix = 'pakchunk'
PakchunkFilenameSuffix = '.pak'

pakchunkRefnameRegexCompiled = None

def getPakContentDir(pakDir, gameName):
    return normPath(os.path.join(pakDir, gameName, 'Content'))


def getPakchunkRefnameRegex():
    global pakchunkRefnameRegexCompiled

    if pakchunkRefnameRegexCompiled is None:
        pakchunkRefnameRegexCompiled = re.compile(
            r'^'
            r'pakchunk(?P<number>0|[1-9]\d*)'
            r'(?P<name>[a-z_-]([\w-]|\.[\w-])*?)??'
            r'(?P<platformPart>-'
                r'(?P<platform>[a-z_](\w|\.\w)*?)'
                r'(?P<platformSuffixPart>-'
                    r'(?P<platformSuffix>\w(\w|\.\w)*?)'
                r')?'
            r')?'
            r'(?P<suffix>.pak)?'
            r'$',
            re.IGNORECASE,
        )
    return pakchunkRefnameRegexCompiled


def pakchunkRefnameToParts(filenameOrStem):
    match = getPakchunkRefnameRegex().match(filenameOrStem)
    if match:
        result = match.groupdict()
        result['number'] = int(result['number'])
        return result


def pakchunkRefnamePartsToRefname(pakNumber, pakName=None, platform=None, platformSuffix=None, addPrefix=True, addSuffix=True):
    stem = f'{pakNumber}{pakName or ""}'
    if addPrefix:
        stem = f'{PakchunkFilenamePrefix}{stem}'
    if platform:
        stem = f'{stem}-{platform}'
    if platformSuffix:
        assert platform
        stem = f'{stem}-{platformSuffix}'
    if addSuffix:
        filename = f'{stem}{PakchunkFilenameSuffix}'
    else:
        filename = stem

    return filename


def pakchunkRefnamePartsDictToRefname(filenameParts, addPrefix=True, addPlatform=True, defaultPlatform=None, addSuffix=True):
    return pakchunkRefnamePartsToRefname(
        filenameParts['number'],
        pakName=filenameParts.get('name', None),
        platform=filenameParts.get('platform', defaultPlatform) if addPlatform else None,
        platformSuffix=filenameParts.get('platformSuffix', None) if addPlatform else None,
        addPrefix=addPrefix,
        addSuffix=addSuffix,
    )


def pakchunkRefnameToFilename(refname, addPrefix=True, addPlatform=True, defaultPlatform=None, addSuffix=True):
    filenameParts = pakchunkRefnameToParts(refname)
    if filenameParts:
        return pakchunkRefnamePartsDictToRefname(
            filenameParts,
            addPrefix=addPrefix,
            addPlatform=addPlatform,
            defaultPlatform=defaultPlatform,
            addSuffix=addSuffix,
        )


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

    fileStem = f'{ProgramName}_UnrealPak_filelist'

    if usingTempFile:
        with openTemporaryFile(
            prefix=f'{fileStem}_',
            suffix='.txt',
            mode='w',
            dir=programPathInfo['dir'],
        ) as file:
            runCommand(file)
    else:
        responseFilePath = normPath(os.path.join(programPathInfo['dir'], f'{fileStem}.txt'))
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
