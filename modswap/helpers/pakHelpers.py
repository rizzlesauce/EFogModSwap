import os
import re

from modswap.metadata.programMetaData import ProgramName

from .consoleHelpers import esprint, sprint, sprintP, sprintPad
from .pathHelpers import getPathInfo, normPath
from .processHelpers import runCall, runCommand
from .tempFileHelpers import openTemporaryFile

DefaultPlatform = 'WindowsNoEditor'

UnrealPakProgramStem = 'UnrealPak'
UnrealPakProgramFilename = f'{UnrealPakProgramStem}.exe'

PakchunkFilenamePrefix = 'pakchunk'
PakchunkFilenameSuffix = '.pak'
PakchunkSigFilenameSuffix = '.sig'

pakchunkRefnameRegexCompiled = None

def getPakContentDir(pakDir, gameName):
    return normPath(os.path.join(pakDir, gameName, 'Content'))


def getPakchunkRefnameRegex():
    global pakchunkRefnameRegexCompiled

    if pakchunkRefnameRegexCompiled is None:
        pakchunkRefnameRegexCompiled = re.compile(
            r'^'
            r'pakchunk(?P<number>0|[1-9]\d*)'
            r'(?P<name>[()a-z_-]([ ()\w-]|\.[()\w-])*?)??'
            r'(?P<platformPart>-'
                r'(?P<platform>[a-z_](\w|\.\w)*?)'
                r'(?P<platformSuffixPart>-'
                    r'(?P<platformSuffix>\w(\w|\.\w)*?)'
                r')?'
            r')?'
            r'(?P<suffix>.(pak|sig))?'
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


def pakchunkToSigFilePath(path):
    if path.lower().endswith(PakchunkFilenameSuffix):
        path = path[:-len(PakchunkFilenameSuffix)]

    return f'{path}{PakchunkSigFilenameSuffix}'


def unrealPak(pakDir, destPakPath, unrealPakPath, compress=True, debug=False, extraCompressionSettings=True, checkInput=None):
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

    def runCommandLocal(responseFile):
        if debug:
            sprintPad()
            sprint(f'Running UnrealPak')
            sprint(f'Response file content: `{responseFileContent}`')
            sprint(f'Writing response file content to "{normPath(responseFile.name)}"')
            sprintPad()

        responseFile.write(responseFileContent)
        responseFile.close()

        args = [
            getPathInfo(destPakPath)['absolute'],
            f'-create={normPath(responseFile.name)}',
        ]
        if compress:
            args.append('-compress')

            if extraCompressionSettings:
                args.append('-asynccompression')
                args.append('-compressionformat=Oodle')
                args.append('-compressmethod=Leviathan')
                args.append('-compresslevel=6')
                args.append('-compressionblocksize=256KB')
                args.append('-multiprocess')

        if debug:
            sprintPad()
            sprintP(args)
            sprintPad()

        if True:
            commandReturnCode = None
            commandError = None
            for commandStreamName, commandLine, commandStop in runCommand(
                programPath,
                args,
                cwd=programPathInfo['dir'],
            ):
                if checkInput is not None and not checkInput():
                    commandStop()
                if commandStreamName == 'return_code':
                    commandReturnCode = commandLine
                elif commandStreamName == 'stderr':
                    if commandError is None or commandError is True:
                        commandError = commandLine or True
                    if debug:
                        sprintPad()
                        esprint(commandLine or '[stderr].')
                        sprintPad()
                elif debug:
                    sprint(commandLine)

            if commandReturnCode:
                quoted = [f'"{arg}"' for arg in [programPath, *args]]
                raise ValueError(f'subprocess call failed: cwd="{programPathInfo["dir"]}" {" ".join(quoted)}. Exit code: {commandReturnCode}. Error: {commandError}')

            if debug:
                sprint(f'Exit code: {commandReturnCode}')
        else:
            runCall([programPath, *args], cwd=programPathInfo['dir'])

    usingTempFile = True

    fileStem = f'{ProgramName}_UnrealPak_filelist'

    if usingTempFile:
        with openTemporaryFile(
            prefix=f'{fileStem}_',
            suffix='.txt',
            mode='w',
            dir=programPathInfo['dir'],
            encoding='utf-8',
        ) as file:
            runCommandLocal(file)
    else:
        responseFilePath = normPath(os.path.join(programPathInfo['dir'], f'{fileStem}.txt'))
        with open(responseFilePath, 'w', encoding='utf-8') as file:
            runCommandLocal(file)

    # TODO: do we need to use gamepath.txt or do anything with *.sig files here?

    return responseFilePath


def unrealUnpak(pakPath, destDir, gameName, unrealPakPath, checkInput=None, debug=False):
    pakPathInfo = getPathInfo(pakPath)
    programPathInfo = getPathInfo(unrealPakPath)
    programFilename = programPathInfo['basename']
    programPath = normPath(os.path.join(programPathInfo['dir'], programFilename))
    destDirPathInfo = getPathInfo(destDir)
    actualDestDir = getPakContentDir(destDirPathInfo['absolute'], gameName)
    if not os.path.exists(actualDestDir):
        os.makedirs(actualDestDir, exist_ok=True)

    args = [
        pakPathInfo['absolute'],
        '-Extract',
        actualDestDir,
    ]

    # no need for this because we construct the base files ahead of time. TODO: use this so we don't have to create the base folder hierarchy.
    extractingToMountPoint = False
    if extractingToMountPoint:
        args.append('-extracttomountpoint')

    if True:
        commandReturnCode = None
        commandError = None
        for commandStreamName, commandLine, commandStop in runCommand(
            programPath,
            args,
            cwd=programPathInfo['dir'],
        ):
            if checkInput is not None and not checkInput():
                commandStop()
            if commandStreamName == 'return_code':
                commandReturnCode = commandLine
            elif commandStreamName == 'stderr':
                if commandError is None or commandError is True:
                    commandError = commandLine or True
                if debug:
                    sprintPad()
                    esprint(commandLine or '[stderr].')
                    sprintPad()
            elif debug:
                sprint(commandLine)

        if commandReturnCode:
            quoted = [f'"{arg}"' for arg in [programPath, *args]]
            raise ValueError(f'subprocess call failed: cwd="{programPathInfo["dir"]}" {" ".join(quoted)}. Exit code: {commandReturnCode}. Error: {commandError}')

        if debug:
            sprint(f'Exit code: {commandReturnCode}')
    else:
        runCall([programPath, *args], cwd=programPathInfo['dir'])
