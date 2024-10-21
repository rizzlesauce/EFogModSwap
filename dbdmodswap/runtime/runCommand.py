import copy
import json
import os
import pathlib
import shutil
import tempfile
import traceback
from itertools import combinations

import yaml

from dbdmodswap.helpers.attachmentHelpers import (basicAttachmentTemplate,
                                                  getAttachmentDisplayName,
                                                  getAttachmentFilename)
from dbdmodswap.helpers.consoleHelpers import (clearSprintRecording, confirm,
                                               confirmOverwrite, esprint,
                                               getSprintIsRecording,
                                               oneLinePrinter,
                                               promptToContinue,
                                               replaySprintRecording, sprint,
                                               sprintClear, sprintPad,
                                               sprintput, startSprintRecording)
from dbdmodswap.helpers.customizationItemDbHelpers import (
    CustomizationItemDbAssetName, ECustomizationCategoryName,
    ECustomizationCategoryNamePrefix, ModelDisplayNamePropNameFieldName,
    addAllToNameMap, findSocketAttachmentsStruct, generateRandomHexString,
    getModelDisplayNameProperty, getModelIdProperty, getModelName,
    getSocketAttachments, getUiDataValues, md5Hash, setModelName, sha256Hash)
from dbdmodswap.helpers.fileHelpers import listFilesRecursively
from dbdmodswap.helpers.gameHelpers import (getGameIsRunning,
                                            getGameLobbyIsRunning,
                                            getGamePaksDir,
                                            getGameServerIsRunning, killGame,
                                            killGameLobby, killGameServer,
                                            openGameLauncher)
from dbdmodswap.helpers.jsonHelpers import jsonDump, jsonifyDataRecursive
from dbdmodswap.helpers.pakHelpers import (DefaultPlatform,
                                           PakchunkFilenameSuffix,
                                           getPakContentDir,
                                           pakchunkRefnamePartsDictToRefname,
                                           pakchunkRefnamePartsToRefname,
                                           pakchunkRefnameToFilename,
                                           pakchunkRefnameToParts, unrealPak,
                                           unrealUnpak)
from dbdmodswap.helpers.pathHelpers import getPathInfo, normPath
from dbdmodswap.helpers.settingsHelpers import (DefaultAttachmentsDir,
                                                DefaultPakingDir,
                                                findSettingsFiles,
                                                getContentDirRelativePath,
                                                getResultsFilePath,
                                                getSettingsTemplate)
from dbdmodswap.helpers.uassetHelpers import (ItemTypeName, NameFieldName,
                                              ValueFieldName, findEnumByType,
                                              findNextItemByFields,
                                              findNextItemByType, getEnumValue,
                                              getPropertyValue, jsonToUasset,
                                              setPropertyValue, uassetToJson)
from dbdmodswap.helpers.unrealEngineHelpers import (
    UnrealEngineCookedSplitFileExtensions, getUnrealProjectCookedContentDir)
from dbdmodswap.helpers.windowsHelpers import (getIsRunningAsAdmin, openFolder,
                                               setConsoleTitle)
from dbdmodswap.helpers.yamlHelpers import yamlDump
from dbdmodswap.metadata.programMetaData import ConsoleTitle

DefaultLauncherStartsGame = True

def mergeSettings(parentData, childData):
    for key, value in childData.items():
        # TODO: merge data instead of overwriting
        parentData[key] = childData[key]


def readSettingsRecursive(filePath, relativeDir='.', silent=False):
    resultData = {}

    pathInfo = getPathInfo(filePath, relativeDir=relativeDir)
    filePath = pathInfo['best']

    if not silent:
        sprint(f'Reading settings from "{filePath}"')
    if not os.path.isfile(filePath):
        raise ValueError(f'Could not read settings from "{filePath}" (file not found)')

    with open(filePath, 'r') as file:
        data = yaml.safe_load(file)

    # TODO: ensure relative paths in settings are converted to relative paths
    # to relativeDir

    for otherPath in data.get('import', []):
        # import paths are relative to the file importing them
        otherData = readSettingsRecursive(otherPath, relativeDir=pathInfo['dir'], silent=silent)
        mergeSettings(resultData, otherData)

    mergeSettings(resultData, data)

    return resultData


def runCommand(**kwargs):
    """ Main entry point of the app """

    settingsFilePath = kwargs.get('settingsFilePath', '')
    activeModConfigName = kwargs.get('activeModConfigName', '')
    inspecting = kwargs.get('inspecting', False)
    creatingAttachments = kwargs.get('creatingAttachments', False)
    extractingAttachments = kwargs.get('extractingAttachments', False)
    renamingAttachmentFiles = kwargs.get('renamingAttachmentFiles', False)
    mixingAttachments = kwargs.get('mixingAttachments', False)
    paking = kwargs.get('paking', False)
    installingMods = kwargs.get('installingMods', False)
    openingGameLauncher = kwargs.get('openingGameLauncher', False)
    killingGame = kwargs.get('killingGame', False)
    nonInteractive = kwargs.get('nonInteractive', False)
    debug = kwargs.get('debug', False)
    uassetGuiPath = kwargs.get('uassetGuiPath', '')
    unrealPakPath = kwargs.get('unrealPakPath', '')
    overwriteOverride = kwargs.get('overwriteOverride', None)
    launcherStartsGame = kwargs.get('launcherStartsGame', None)
    fromMenu = kwargs.get('fromMenu', False)
    dryRun = kwargs.get('dryRun', False)
    gameDir = kwargs.get('gameDir', None)
    pakingDir = kwargs.get('pakingDir', None)
    attachmentsDir = kwargs.get('attachmentsDir', None)
    unrealProjectDir = kwargs.get('unrealProjectDir', None)

    DryRunPrefix = '[DryRun] '
    dryRunPrefix = DryRunPrefix if dryRun else ''

    launcherClearsScreenBuffer = False
    if launcherStartsGame is None:
        launcherStartsGame = DefaultLauncherStartsGame

    if openingGameLauncher and not dryRun and launcherClearsScreenBuffer:
        startSprintRecording()

    # TODO: remove -- too verbose
    printingJson = False
    printingYaml = False

    writingUnalteredDb = True
    writingAlteredDb = True

    exitCode = 0

    warnings = []
    def printWarning(message, pad=True):
        warnings.append(str(message))
        if pad:
            sprintPad()
        sprint(f'WARN: {message}')
        if pad:
            sprintPad()

    errors = []
    def printError(error, pad=True):
        nonlocal exitCode

        exitCode = 1

        if isinstance(error, Exception):
            traceLines = traceback.format_exception(error)
            lines = traceback.format_exception_only(error)
        elif isinstance(error, list):
            lines = error
            traceLines = lines
        else:
            lines = [error]
            traceLines = lines

        for line in traceLines:
            errors.append(str(line))

        if pad:
            sprintPad()

        for line in (traceLines if debug else lines):
            esprint(f'ERROR: {line}')

        if pad:
            sprintPad()

    if killingGame:
        sprintPad()
        sprint(f'{dryRunPrefix}Killing game...')
        if getGameIsRunning():
            didIt = False
            if not dryRun:
                killExitCode = killGame()
                if killExitCode:
                    printError(f'killing game returned exit code: {killExitCode}')
                else:
                    didIt = True
            if didIt:
                sprint(f'{dryRunPrefix}Game process terminated.')
            # TODO: need to wait?
        else:
            sprint('Game is not running.')
        sprintPad()
        sprint(f'{dryRunPrefix}Killing game lobby...')
        if getGameLobbyIsRunning():
            shouldDoIt = True
            if not getIsRunningAsAdmin():
                sprint('Must gain elevated access to kill lobby')
                if nonInteractive:
                    printError('Cannot gain elevated access in non-interactive mode')
                else:
                    shouldDoIt = confirm('continue to UAC', emptyMeansNo=False)

            if shouldDoIt:
                didIt = False
                if not dryRun:
                    killExitCode = killGameLobby()
                    if killExitCode:
                        printError(f'killing lobby returned exit code: {killExitCode}')
                    else:
                        didIt = True
                if didIt:
                    sprint(f'{dryRunPrefix}Lobby process terminated.')
                    # TODO: need to wait?
            else:
                sprint('Skipping killing lobby.')
        else:
            sprint('Lobby is not running.')
        sprintPad()
        sprint(f'{dryRunPrefix}Killing game server...')
        if getGameServerIsRunning():
            didIt = False
            if not dryRun:
                killExitCode = killGameServer()
                if killExitCode:
                    printError(f'killing server returned exit code: {killExitCode}')
                else:
                    didIt = True
            if didIt:
                sprint(f'{dryRunPrefix}Server process terminated.')
            # TODO: need to wait?
        else:
            sprint('Server is not running.')
        sprintPad()

    if False:
        importAttachmentsSeparator = 'And'
    else:
        importAttachmentsSeparator = '_'

    exportAttachmentsSeparator = '_'

    settingsDirPathInfo = getPathInfo('.')
    discoveredSettingsFiles = []

    if inspecting:
        sprintPad()
        sprint(f'Scanning "{settingsDirPathInfo["best"]}" for settings files...')
        for filename in findSettingsFiles(settingsDirPathInfo['absolute']):
            discoveredSettingsFiles.append(filename)
            sprint(f'{len(discoveredSettingsFiles)} - {filename}')
        sprint('Done.', end=' ')
        sprint(f'Discovered {len(discoveredSettingsFiles)} settings files.')
        sprintPad()

    settingsFilePath = getPathInfo(settingsFilePath)['best']
    settings = {}

    cookedContentDir = ''
    cookedContentPaths = []
    cookedContentAssetPathsMap = {}
    gamePaksDir = ''
    gamePakchunks = []
    modConfigNameGroupsMap = {}
    modGroupNamePakchunksMap = {}
    reservedPakchunks = None
    targetActiveMods = []
    pakingDirPakchunkStems = []
    gameName = ''
    srcPakPath = ''
    srcPakStem = ''
    srcPakDir = ''
    srcPakNumber = -1
    srcPakName = None
    srcPakPlatform = None
    srcPakPlatformSuffix = None
    srcContentDir = ''
    srcPakContentDir = ''
    srcPakContentPaths = []
    srcPakContentAssetPathsMap = {}
    destPakNumber = None
    destPakName = ''
    destPakPlatformSuffix = ''
    destPakAssets = None

    destPakStem = ''
    destPakDir = ''
    destPakContentDir = ''
    destPakPath = ''

    destPlatform = DefaultPlatform

    customizationItemDbPath = ''
    customizationItemDbJsonPath = ''
    customizationItemDb = None

    equivalentParts = {}
    supersetParts = {}
    mutuallyExclusive = {}
    attachmentConflicts = {}
    combosToSkip = {}

    combinationsAdded = {}
    combinationsSkipped = {}
    attachmentsToMix = {}
    nameMapNamesRemoved = []
    nameMapNamesAdded = []
    attachmentsCreated = []
    nameMapArray = []
    nameMapSet = set(nameMapArray)
    attachmentsRenamed = {}

    dryRunDirsCreated = {}

    def ensureDir(dir, title='Folder', warnIfNotExist=True):
        dir = getPathInfo(dir)['best']
        if not os.path.exists(dir) and (not dryRun or dir not in dryRunDirsCreated):
            if warnIfNotExist or dryRun:
                printWarning(f'{title or "Folder"} ("{dir}") does not exist. {dryRunPrefix}Creating it now.')
            shouldWrite = not dryRun or (not nonInteractive and confirm(f'Create folder "{dir}" despite dry run', pad=True, emptyMeansNo=True))
            written = False
            if shouldWrite:
                os.makedirs(dir, exist_ok=True)
                written = True
            if (written or dryRun) and warnIfNotExist or dryRun:
                sprint(f'{dryRunPrefix if not written else ""}Done writing.')
                sprintPad()
            if dryRun:
                dryRunDirsCreated.add(dir)
        return dir

    def ensureAttachmentsDir():
        return ensureDir(attachmentsDir, '`attachmentsDir`')

    def ensurePakingDir():
        return ensureDir(pakingDir, '`pakingDir`')

    def readyToWrite(path, delete=True, overwrite=None, dryRunHere=None):
        path = getPathInfo(path)['best']

        if dryRunHere is None:
            dryRunHere = dryRun

        dryRunPrefixHere = DryRunPrefix if dryRunHere else ''

        if not os.path.exists(path):
            return True

        shouldWarn = True

        if overwrite is not None:
            result = overwrite
        elif overwriteOverride is not None:
            result = overwriteOverride
        elif nonInteractive:
            printWarning('Cannot confirm file overwrite in non-interactive mode')
            result = False
        else:
            result = confirmOverwrite(path, prefix=dryRunPrefixHere, emptyMeansNo=True)
            shouldWarn = False

        if result:
            if shouldWarn or dryRunHere:
                printWarning(f'{dryRunPrefixHere}Overwriting "{path}"')
        elif shouldWarn:
            printWarning(f'Skipping write of "{path}" (file exists)')

        if result and delete and not dryRunHere:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                pathlib.Path.unlink(path)

        return result

    def checkAttachmentName(category, attachmentName, otherInfo=None):
        if attachmentName not in attachmentsToMix.get(category, {}):
            printWarning(f"reference to missing attachment: {category}::{attachmentName}{' (' if otherInfo else ''}{otherInfo or ''}{')' if otherInfo else ''}")

    try:
        if not os.path.exists(settingsFilePath):
            printWarning(f'Settings file ("{settingsFilePath}") does not exist. {dryRunPrefix}Creating it now with default content.')
            yamlStringContent = getSettingsTemplate(
                gameDir=gameDir,
                pakingDir=pakingDir,
                attachmentsDir=attachmentsDir,
                unrealProjectDir=unrealProjectDir,
                uassetGuiPath=uassetGuiPath,
                unrealPakPath=unrealPakPath,
            )
            if printingYaml:
                sprint(yamlStringContent)
                sprintPad()
            shouldWrite = not dryRun or (not nonInteractive and confirm(f'write settings file ("{settingsFilePath}") despite dry run', pad=True, emptyMeansNo=True))
            written = False
            if shouldWrite:
                with open(settingsFilePath, 'w') as file:
                    file.write(yamlStringContent)
                    written = True
            if written or dryRun:
                sprint(f'{dryRunPrefix if not written else ""}Done writing.')
            sprintPad()

        settingsPathInfo = getPathInfo(settingsFilePath)
        settingsDir = settingsPathInfo['dir']
        settings = readSettingsRecursive(settingsFilePath)

        if not unrealPakPath:
            unrealPakPath = settings.get('unrealPakPath', '')
        unrealPakPath = unrealPakPath or ''
        unrealPakPath = getPathInfo(unrealPakPath)['best']
        if not unrealPakPath:
            if (
                inspecting
                or paking
                or (
                    srcPakPath and (
                        extractingAttachments
                        or mixingAttachments
                    )
                )
            ):
                printWarning('Missing or empty `unrealPakPath`')
        elif not os.path.isfile(unrealPakPath):
            printError(f'`unrealPakPath` is not a file ("{unrealPakPath}")')
            unrealPakPath = ''

        if not uassetGuiPath:
            uassetGuiPath = settings.get('uassetGuiPath', '')
        uassetGuiPath = uassetGuiPath or ''
        uassetGuiPath = getPathInfo(uassetGuiPath)['best']
        if not uassetGuiPath:
            if (
                inspecting
                or (
                    customizationItemDbPath
                    and (
                        extractingAttachments
                        or mixingAttachments
                    )
                )
            ):
                printWarning('Missing or empty `uassetGuiPath`')
        elif not os.path.isfile(uassetGuiPath):
            printError(f'`uassetGuiPath` is not a file ("{uassetGuiPath}")')
            uassetGuiPath = ''

        if not pakingDir:
            pakingDir = settings.get('pakingDir', '')
        pakingDir = pakingDir or ''
        pakingDir = getPathInfo(pakingDir)['best']
        if not pakingDir:
            pakingDir = getPathInfo(DefaultPakingDir)['best']
            if (
                inspecting
                or extractingAttachments
                or mixingAttachments
                or paking
                or installingMods
            ):
                printWarning(f'Missing or empty `pakingDir`. Defaulting to "{pakingDir}"')

        if not attachmentsDir:
            attachmentsDir = settings.get('attachmentsDir', '')
        attachmentsDir = attachmentsDir or ''
        attachmentsDir = getPathInfo(attachmentsDir)['best']
        if not attachmentsDir:
            attachmentsDir = getPathInfo(DefaultAttachmentsDir)['best']
            if (
                inspecting
                or extractingAttachments
                or creatingAttachments
                or renamingAttachmentFiles
                or mixingAttachments
            ):
                printWarning(f'Missing or empty `attachmentsDir`. Defaulting to "{attachmentsDir}"')

        if not gameDir:
            gameDir = settings.get('gameDir', '')
        gameDir = gameDir or ''
        gameDir = getPathInfo(gameDir)['best']
        if not gameDir:
            if inspecting:
                printWarning('Missing or empty `gameDir`')
        elif not os.path.isdir(gameDir):
            printError(f'`gameDir` is not a directory ("{gameDir}")')
            gameDir = ''

        if not gameName:
            gameName = settings.get('gameName', '')
        gameName = gameName.strip()
        if not gameName and inspecting:
            printWarning('Missing or empty `gameName`')

        if not unrealProjectDir:
            unrealProjectDir = settings.get('unrealProjectDir', '')
        unrealProjectDir = unrealProjectDir or ''
        unrealProjectDir = getPathInfo(unrealProjectDir)['best']
        if not unrealProjectDir:
            if (
                inspecting
                or extractingAttachments
                or mixingAttachments
                or paking
            ):
                printWarning(f'Missing or empty `unrealProjectDir`')
        elif not os.path.isdir(unrealProjectDir):
            printError(f'`unrealProjectDir` is not a directory ("{unrealProjectDir}")')
            unrealProjectDir = ''

        if not srcPakPath:
            srcPakPath = settings.get('srcPakPath', '')
        srcPakPath = getPathInfo(srcPakPath)['best']
        if not srcPakPath and inspecting:
            printWarning(f'Missing or empty `srcPakPath`')

        if not customizationItemDbPath:
            customizationItemDbPath = settings.get('customizationItemDbPath', '')
        customizationItemDbPath = customizationItemDbPath.strip()
        if not customizationItemDbPath and inspecting:
            printWarning(f'Missing or empty `customizationItemDbPath`')

        if destPakNumber is None:
            destPakNumber = int(settings.get('destPakNumber', -1))
        if destPakNumber < 0 and (
            inspecting
            or paking
        ):
            printWarning(f'Missing, empty, or invalid `destPakNumber`')

        if not destPakName:
            destPakName = settings.get('destPakName', '')
        destPakName = destPakName.strip()
        if not destPakName and (
            inspecting
            or paking
        ):
            printWarning(f'Missing or empty `destPakName`')

        if destPakAssets is None:
            destPakAssets = settings.get('destPakAssets', None)
        if destPakAssets is None:
            if inspecting:
                printWarning('Missing `destPakAssets`')
            destPakAssets = []
        elif not destPakAssets:
            if inspecting or paking:
                printWarning('Empty `destPakAssets`')
        else:
            destPakAssets = [getPathInfo(p)['normalized'] for p in destPakAssets]

        if not activeModConfigName:
            activeModConfigName = settings.get('activeModConfig', '')
        activeModConfigName = (activeModConfigName or '').strip()
        if not activeModConfigName:
            message = 'No active mod config (missing `activeModConfig`)'
            if installingMods:
                printError(message)
            elif inspecting:
                printWarning(message)

        if not modConfigNameGroupsMap:
            modConfigNameGroupsMap = settings.get('modConfigs', {})
        if not modConfigNameGroupsMap:
            message = 'Missing or empty `modConfigs`'
            if installingMods:
                printError(message)
            elif inspecting:
                printWarning(message)

        if not modGroupNamePakchunksMap:
            modGroupNamePakchunksMap = settings.get('modGroups', {})
        if not modGroupNamePakchunksMap:
            message = 'Missing or empty `modGroups`'
            if installingMods:
                printError(message)
            elif inspecting:
                printWarning(message)

        if reservedPakchunks is None:
            reservedPakchunks = settings.get('reservedPakchunks', [])
        if not reservedPakchunks:
            printWarning(f'Missing or empty `reservedPakchunks`')

        if not equivalentParts:
            equivalentParts = settings.get('equivalentParts', {})
        if not equivalentParts and inspecting:
            printWarning('Missing or empty `equivalentParts`')

        if not supersetParts:
            supersetParts = settings.get('supersetParts', {})
        if not supersetParts and inspecting:
            printWarning('Missing or empty `supersetParts`')

        if not mutuallyExclusive:
            mutuallyExclusive = settings.get('mutuallyExclusive', {})
        if not mutuallyExclusive and inspecting:
            printWarning('Missing or empty `mutuallyExclusive`')

        if not attachmentConflicts:
            attachmentConflicts = settings.get('attachmentConflicts', {})
        if not attachmentConflicts and inspecting:
            printWarning('Missing or empty `attachmentConflicts`')

        if not combosToSkip:
            combosToSkip = settings.get('combosToSkip', [])
        if not combosToSkip and inspecting:
            printWarning('Missing or empty `combosToSkip`')

        if creatingAttachments:
            if nonInteractive:
                printWarning('Cannot create attachment definition in non-interactive mode')
            else:
                done = False
                canceled = False

                def confirmCanceled():
                    nonlocal canceled
                    canceled = True
                    return canceled

                sprintPad()
                sprint('Adding attachment definition...')
                sprintPad()
                ensureAttachmentsDir()
                while not done:
                    attachment = copy.deepcopy(basicAttachmentTemplate)
                    attachment['modelCategory'] = ''
                    categoryOptions = {'SurvivorTorso', 'SurvivorLegs', 'SurvivorHead'}
                    while not attachment['modelCategory']:
                        attachment['modelCategory'] = sprintput(f"Model category ({', '.join(categoryOptions)}): ").strip()
                        if not attachment['modelCategory']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        if attachment['modelCategory'] not in categoryOptions:
                            esprint('ERROR: unsupported category')
                            attachment['modelCategory'] = ''

                    if canceled:
                        break

                    attachment['attachmentId'] = ''
                    while not attachment['attachmentId']:
                        attachment['attachmentId'] = sprintput('Attachment ID: ').strip()
                        if not attachment['attachmentId']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        filename = getAttachmentFilename(attachment['attachmentId'])
                        filePath = normPath(os.path.join(ensureAttachmentsDir(), filename))
                        if os.path.exists(filePath):
                            esprint('ERROR: attachment ID already exists')
                            attachment['attachmentId'] = ''

                    if canceled:
                        break

                    attachment['displayName'] = ''
                    while not attachment['displayName']:
                        attachment['displayName'] = sprintput('Display name: ').strip()
                        if not attachment['displayName']:
                            #  allow it to be empty
                            break

                    if canceled:
                        break

                    values = getPropertyValue(attachment['attachmentData'])
                    blueprintAttachment = findNextItemByFields(
                        values,
                        [
                            ItemTypeName,
                            NameFieldName,
                        ],
                        [
                            'UAssetAPI.PropertyTypes.Objects.SoftObjectPropertyData, UAssetAPI',
                            'AttachementBlueprint',
                        ]
                    )
                    assetPath = getPropertyValue(blueprintAttachment)['AssetPath']
                    assetPath['AssetName'] = ''
                    while not assetPath['AssetName']:
                        assetPath['AssetName'] = sprintput('Blueprint path: ').strip()
                        if not assetPath['AssetName']:
                            if confirmCanceled():
                                break
                            else:
                                continue

                        if not assetPath['AssetName'].startswith('/Game/'):
                            esprint('ERROR: should start with `/Game/`')
                            assetPath['AssetName'] = ''
                            continue

                        try:
                            path = pathlib.PurePosixPath(assetPath['AssetName'])
                        except:
                            esprint('ERROR: invalid game path')
                            assetPath['AssetName'] = ''
                            continue

                        if assetPath['AssetName'].endswith('/'):
                            esprint('ERROR: should not be a directory')
                            assetPath['AssetName'] = ''
                            continue

                        stem = path.stem
                        if not stem:
                            esprint('ERROR: invalid name')
                            assetPath['AssetName'] = ''
                            continue

                        suffix = f'.{stem}_C'
                        if path.suffix:
                            if path.suffix != suffix:
                                esprint('ERROR: invalid path suffix. Should be {suffix}')
                                assetPath['AssetName'] = ''
                                continue
                        else:
                            path = path.with_name(f'{stem}{suffix}')

                        normalizedPath = path.as_posix()
                        sprint(f'Normalized path: {normalizedPath}')
                        assetPath['AssetName'] = normalizedPath

                    if canceled:
                        break

                    sprint(f'{dryRunPrefix}Writing attachment definition to "{filePath}"')
                    shouldWrite = not dryRun or (not nonInteractive and confirm(f'write attachment definition ("{filePath}") despite dry run', pad=True, emptyMeansNo=True))
                    written = False
                    if shouldWrite:
                        if readyToWrite(filePath, dryRunHere=False):
                            with open(filePath, 'w') as file:
                                yamlDump(attachment, file)
                                written = True
                    if written or dryRun:
                        sprint(f'{dryRunPrefix if not written else ""}Done writing.')
                    sprintPad()

                    if not confirm('add another', emptyMeansNo=True):
                        done = True

                if canceled:
                    sprintPad()
                    sprint(f'Add canceled.')
                    sprintPad()

        if (inspecting or extractingAttachments or mixingAttachments or paking) and srcPakPath:
            sprintPad()
            sprint(f'Resolving source pak content folder...')
            if not gameName:
                printError(f'Cannot resolve source pak content folder (missing `gameName`)')
            else:
                if not os.path.exists(srcPakPath):
                    if not pathlib.Path(srcPakPath).suffix:
                        srcPakPath = f'{srcPakPath}{PakchunkFilenameSuffix}'
                        printWarning(f'Trying `srcPakPath` with "{PakchunkFilenameSuffix}" extension ("{srcPakPath})')

                if not os.path.exists(srcPakPath):
                    printError(f'`srcPakPath` ("{srcPakPath}") does not exist')
                elif os.path.isdir(srcPakPath):
                    srcPakDir = srcPakPath
                elif pathlib.Path(srcPakPath).suffix.lower() == PakchunkFilenameSuffix:
                    srcPakPathInfo = getPathInfo(srcPakPath)
                    srcPakDir = getPathInfo(os.path.join(ensurePakingDir(), srcPakPathInfo['stem']))['best']
                    sprintPad()
                    sprint(f'{dryRunPrefix}Unpaking "{srcPakPath}" to "{srcPakDir}')
                    if os.path.exists(unrealPakPath):
                        ensurePakingDir()
                        shouldWrite = not dryRun or (not nonInteractive and confirm(f'write to source pak folder ("{srcPakDir}") despite dry run', pad=True, emptyMeansNo=True))
                        written = False
                        if shouldWrite:
                            if readyToWrite(srcPakDir, dryRunHere=False):
                                unrealUnpak(srcPakPath, srcPakDir, gameName, unrealPakPath)
                                written = True
                        if written or dryRun:
                            sprint(f'{dryRunPrefix if not written else ""}Done unpaking.')
                        sprintPad()
                    else:
                        printError(f'`unrealPakPath` ("{unrealPakPath})" does not exist')

                if srcPakDir:
                    srcPakPathInfo = getPathInfo(srcPakDir)
                    srcPakStem = srcPakPathInfo['stem']
                    srcPakFilenameParts = pakchunkRefnameToParts(srcPakStem)
                    if srcPakFilenameParts:
                        srcPakNumber = srcPakFilenameParts['number']
                        srcPakName = srcPakFilenameParts.get('name', '')
                        srcPakPlatform = srcPakFilenameParts.get('platform', '')
                        srcPakPlatformSuffix = srcPakFilenameParts.get('platformSuffix', '')
                        if not srcPakName:
                            printWarning('Source pakchunk filename has no name')
                        if not srcPakPlatform:
                            printWarning('Source pakchunk filename has no platform')
                        elif srcPakPlatform != destPlatform:
                            printWarning(f'Source pakchunk platform ("{srcPakPlatform}") is different than "{destPlatform}"')
                    srcPakContentDir = getPakContentDir(srcPakDir, gameName)
                    sprintPad()
                    sprint(f'Reading pak content at "{srcPakContentDir}"')
                    if os.path.isdir(srcPakContentDir):
                        for pathIndex, path in enumerate(listFilesRecursively(srcPakContentDir)):
                            srcPakContentPaths.append(path)
                            suffix = pathlib.Path(path).suffix.lower()
                            if suffix in UnrealEngineCookedSplitFileExtensions:
                                assetPath = path[:-len(suffix)]
                                if assetPath not in srcPakContentAssetPathsMap:
                                    srcPakContentAssetPathsMap[assetPath] = []
                                    if debug:
                                        sprint(f'Asset {len(srcPakContentAssetPathsMap)}: {assetPath}')
                                srcPakContentAssetPathsMap[assetPath].append(suffix)
                            if debug:
                                sprint(f'{pathIndex + 1} - {path}')
                        sprintPad()
                        sprint(f'Discovered {len(srcPakContentAssetPathsMap)} pak assets ({len(srcPakContentPaths)} files).')
                        sprintPad()
                    else:
                        printError(f'Pak content folder ("{srcPakContentDir}") does not exist')
                        srcPakContentDir = ''

        if (inspecting or extractingAttachments or mixingAttachments or paking) and unrealProjectDir:
            if srcPakPath and not inspecting:
                printWarning(f'Not looking for unreal project cooked content because `srcPakDir` has precedence.')
            else:
                sprintPad()
                sprint(f'Resolving unreal project cooked content folder...')
                if not gameName:
                    printError(f'Cannot resolve unreal project cooked content folder (missing `gameName`)')
                else:
                    cookedContentDir = getUnrealProjectCookedContentDir(unrealProjectDir, destPlatform, gameName)
                    sprintPad()
                    sprint(f'Reading cooked content at "{cookedContentDir}"')
                    if os.path.isdir(cookedContentDir):
                        for pathIndex, path in enumerate(listFilesRecursively(cookedContentDir)):
                            cookedContentPaths.append(path)
                            suffix = pathlib.Path(path).suffix.lower()
                            if suffix in UnrealEngineCookedSplitFileExtensions:
                                assetPath = path[:-len(suffix)]
                                if assetPath not in cookedContentAssetPathsMap:
                                    cookedContentAssetPathsMap[assetPath] = []
                                    if debug:
                                        sprint(f'Asset {len(cookedContentAssetPathsMap)}: {assetPath}')
                                cookedContentAssetPathsMap[assetPath].append(suffix)
                            if debug:
                                sprint(f'{pathIndex + 1} - {path}')

                        sprintPad()
                        sprint(f'Discovered {len(cookedContentAssetPathsMap)} cooked assets ({len(cookedContentPaths)} files).')
                        sprintPad()
                    else:
                        printError(f'Cooked content folder ("{cookedContentDir}") does not exist')
                        cookedContentDir = ''

        if (inspecting and customizationItemDbPath) or extractingAttachments or mixingAttachments:
            sprintPad()
            sprint(f'Resolving {CustomizationItemDbAssetName} path...')

            customizationItemDbPath = getPathInfo(customizationItemDbPath)['normalized']
            if not customizationItemDbPath:
                if extractingAttachments or mixingAttachments:
                    printError('Missing or invalid `customizationItemDbPath`')
            else:
                customizationItemDbContentDirRelativePath = getContentDirRelativePath(customizationItemDbPath)
                if customizationItemDbContentDirRelativePath is None:
                    sprint(f'Resolved path: "{customizationItemDbPath}"')
                else:
                    sprint(f'Content folder relative path detected: "{customizationItemDbPath}"')

                    if not getPathInfo(customizationItemDbContentDirRelativePath)['suffixLower']:
                        customizationItemDbContentDirRelativePath = f'{customizationItemDbContentDirRelativePath}.uasset'
                        sprint(f'Adding ".uasset" suffix: "{customizationItemDbContentDirRelativePath}"')

                    customizationItemDbPathUnaltered = customizationItemDbPath
                    customizationItemDbPath = ''

                    allowTryingAsNormalPath = False

                    if not customizationItemDbPath and srcPakPath:
                        if srcPakContentDir:
                            customizationItemDbPath = getPathInfo(os.path.join(srcPakContentDir, customizationItemDbContentDirRelativePath))['best']
                            if not os.path.exists(customizationItemDbPath):
                                printWarning(f'Content dir relative path ("{customizationItemDbPath}") does not exist')
                                customizationItemDbPath = ''
                        else:
                            message = 'Content folder relative path cannot be resolved because `srcPakPath` is missing content'
                            if allowTryingAsNormalPath:
                                printWarning(message)
                            else:
                                printError(message)
                    elif not customizationItemDbPath and unrealProjectDir:
                        if cookedContentDir:
                            customizationItemDbPath = getPathInfo(os.path.join(cookedContentDir, customizationItemDbContentDirRelativePath))['best']
                            if not os.path.exists(customizationItemDbPath):
                                printWarning(f'Content dir relative path ("{customizationItemDbPath}") does not exist')
                                customizationItemDbPath = ''
                        else:
                            message = 'Content folder relative path cannot be resolved because `unrealProjectDir` is missing content'
                            if allowTryingAsNormalPath:
                                printWarning(message)
                            else:
                                printError(message)

                    if customizationItemDbPath:
                        sprint(f'Resolved to "{customizationItemDbPath}".')
                    elif allowTryingAsNormalPath:
                        customizationItemDbPath = customizationItemDbPathUnaltered
                        printWarning(f'Trying `customizationItemDbPath` as normal file path "{customizationItemDbPath}"')

        if customizationItemDbPath:
            customizationItemDbPathInfo = getPathInfo(customizationItemDbPath)
            customizationItemDbSupportedFileTypes = ['.json', '.uasset']
            if customizationItemDbPathInfo['suffixLower'] not in customizationItemDbSupportedFileTypes:
                printError(f'Unsupported file extension for {customizationItemDbPath}: must be one of ({", ".join(customizationItemDbSupportedFileTypes)})')
            elif not os.path.isfile(customizationItemDbPath):
                printWarning(f'`customizationItemDbPath` ("{customizationItemDbPath}") does not exist')
            elif customizationItemDbPathInfo['suffixLower'] == '.json':
                customizationItemDbJsonPath = customizationItemDbPath
            elif customizationItemDbPathInfo['suffixLower'] == '.uasset':
                customizationItemDbJsonPath = getPathInfo(os.path.join(
                    settingsPathInfo['dir'],
                    f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.json",
                ))['best']
                sprintPad()
                sprint(f'{dryRunPrefix}Converting "{customizationItemDbPath}" to JSON, writing "{customizationItemDbJsonPath}"')
                if os.path.exists(uassetGuiPath):
                    shouldWrite = not dryRun or (not nonInteractive and confirm(f'write {CustomizationItemDbAssetName} JSON ("{customizationItemDbJsonPath}") despite dry run', pad=True, emptyMeansNo=True))
                    written = False
                    if shouldWrite:
                        if readyToWrite(customizationItemDbJsonPath, overwrite=True, dryRunHere=False):
                            uassetToJson(customizationItemDbPath, customizationItemDbJsonPath, uassetGuiPath)
                            written = True
                    if written or dryRun:
                        sprint(f'{dryRunPrefix if not written else ""}Done converting.')
                    sprintPad()
                else:
                    printError(f'`uassetGuiPath` ("{uassetGuiPath})" does not exist')
                    customizationItemDbJsonPath = ''
            else:
                raise ValueError('internal error')

            if customizationItemDbJsonPath:
                with oneLinePrinter() as oneLinePrint:
                    sprintPad()
                    oneLinePrint(f'Reading {CustomizationItemDbAssetName} JSON from "{customizationItemDbJsonPath}"...')
                    with open(customizationItemDbJsonPath, 'r') as file:
                        customizationItemDb = json.load(file)
                    oneLinePrint('done.')

                if printingJson:
                    sprintPad()
                    sprint(jsonDump(customizationItemDb, pretty=True))
                    sprintPad()

                if printingYaml:
                    sprintPad()
                    sprint(yamlDump(customizationItemDb))
                    sprintPad()

                if writingUnalteredDb:
                    outPath = getPathInfo(os.path.join(
                        settingsDir,
                        f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.yaml",
                    ))['best']
                    sprintPad()
                    sprint(f'{dryRunPrefix}Writing unaltered {CustomizationItemDbAssetName} to "{outPath}"')
                    shouldWrite = not dryRun
                    written = False
                    if shouldWrite:
                        if readyToWrite(outPath, overwrite=True, dryRunHere=False):
                            with open(outPath, 'w') as file:
                                yamlDump(customizationItemDb, file)
                                written = True
                    if written or dryRun:
                        sprint(f'{dryRunPrefix if not written else ""}Done writing.')
                    sprintPad()

        if inspecting or mixingAttachments or renamingAttachmentFiles:
            sprintPad()
            sprint(f'Reading attachments...')
            attachmentFilenames = os.listdir(ensureAttachmentsDir())
            sprintPad()
            sprint(f'Discovered {len(attachmentFilenames)} attachment files')
            if len(attachmentFilenames):
                for filenameIndex, filename in enumerate(attachmentFilenames):
                    filePath = getPathInfo(os.path.join(ensureAttachmentsDir(), filename))['best']
                    try:
                        if filename.endswith('.yaml') or filename.endswith('.json'):
                            with oneLinePrinter() as printOneLine:
                                printOneLine(f'{filenameIndex + 1} - reading {filename}...')
                                with open(filePath, 'r') as file:
                                    if filename.endswith('.yaml'):
                                        attachmentData = yaml.safe_load(file)
                                    elif filename.endswith('.json'):
                                        attachmentData = json.load(file)
                                    else:
                                        raise ValueError(f'Invalid file type: {filename}')

                                attachmentName = attachmentData['attachmentId']
                                printOneLine(f'loaded {attachmentName}.')

                            if printingJson:
                                sprintPad()
                                sprint(jsonDump(attachmentData, pretty=True))
                                sprintPad()

                            if printingYaml:
                                sprintPad()
                                sprint(yamlDump(attachmentData))
                                sprintPad()

                            categoryName = attachmentData['modelCategory']

                            if attachmentName in attachmentsToMix.get(categoryName, {}):
                                printWarning(f'duplicate attachment {attachmentName}!')

                            if categoryName not in attachmentsToMix:
                                attachmentsToMix[categoryName] = {}
                            attachmentsToMix[categoryName][attachmentName] = attachmentData

                            if renamingAttachmentFiles:
                                newFilename = getAttachmentFilename(attachmentName)
                                if newFilename == filename:
                                    sprint(f'rename not needed (already named correctly).')
                                else:
                                    sprint(f'{dryRunPrefix}Renaming {filename} to {newFilename}')
                                    newFilePath = getPathInfo(os.path.join(ensureAttachmentsDir(), newFilename))['best']
                                    if os.path.exists(newFilePath):
                                        raise ValueError(f'Could not rename {filename} to {newFilename} (file already exists)')

                                    if not dryRun:
                                        os.rename(filePath, newFilePath)
                                    attachmentsRenamed[filename] = newFilename
                    except Exception as e:
                        printError(e)
                sprint('Done loading attachments.')
                sprintPad()

            if mixingAttachments or inspecting:
                sprintPad()
                sprint('Generating exclusion rules...')
                sprintPad()
                if customizationItemDb is not None:
                    nameMapArray = customizationItemDb['NameMap']
                    nameMapSet = set(nameMapArray)

                categoryCombinationsToSkip = {}
                categoryCombinationSubsetsToSkip = {}

                setEqualitySymbol = '=='
                modelRestrictSymbol = ':'
                modelRestrictSeparator = ','

                if debug:
                    sprintPad()
                    sprint('Reading combosToSkip...')

                def logSkip(combo, baseModels=None, category=None, isExact=False, info=''):
                    if baseModels is None:
                        baseModels = []
                    def mySorted(combo):
                        if False:
                            return sorted([n for n in combo])
                        return combo
                    sprint(f"skip {f'{category} ' if (category and False) else ''}combo {'=' if isExact else '⊇'} {','.join(mySorted(combo))}: {','.join(baseModels) or '*'}{f' ({info})' if info else ''}")

                for category, combosList in combosToSkip.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    if category not in categoryCombinationsToSkip:
                        categoryCombinationsToSkip[category] = {}

                    for comboIndex, combo in enumerate(combosList):
                        isSubset = True
                        newCombo = set()
                        baseModels = set()
                        for attachmentIndex, attachment in enumerate(combo):
                            actualAttachment = attachment

                            if modelRestrictSymbol in actualAttachment:
                                markerIndex = actualAttachment.index(modelRestrictSymbol)
                                baseModelsString = actualAttachment[markerIndex + len(modelRestrictSymbol):]
                                if baseModelsString:
                                    for modelId in baseModelsString.split(modelRestrictSeparator):
                                        baseModels.add(modelId)
                                actualAttachment = actualAttachment[:markerIndex]

                            if setEqualitySymbol in actualAttachment:
                                isSubset = False
                                markerIndex = actualAttachment.index(setEqualitySymbol)
                                actualAttachment = actualAttachment[:markerIndex]

                            checkAttachmentName(category, actualAttachment, f'combosToSkip[{comboIndex}][{attachmentIndex}]')
                            newCombo.add(actualAttachment)

                        frozenCombo = frozenset(newCombo)
                        if isSubset:
                            categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset(baseModels)
                        else:
                            categoryCombinationsToSkip[category][frozenCombo] = frozenset(baseModels)
                        if debug:
                            logSkip(frozenCombo, baseModels, isExact=not isSubset, category=category)

                if debug:
                    sprintPad()
                    sprint('Reading mutuallyExclusive...')

                for category, groups in mutuallyExclusive.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for groupIndex, attachments in enumerate(groups):
                        attachmentsSeen = set()
                        for attachmentIndex, attachment in enumerate(attachments):
                            if attachment in attachmentsSeen:
                                printWarning(f'duplicate attachment ID (mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}])')
                            else:
                                checkAttachmentName(category, attachment, f'mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}]')
                                attachmentsSeen.add(attachment)

                        for duo in combinations(set(attachments), 2):
                            frozenDuo = frozenset(duo)
                            categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                            if debug:
                                logSkip(frozenDuo, category=category)

                if debug:
                    sprintPad()
                    sprint('Reading attachmentConflicts...')

                for category, attachmentConflictsMap in attachmentConflicts.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for attachment, conflicts in attachmentConflictsMap.items():
                        checkAttachmentName(category, attachment, f'attachmentConflicts.{category}')
                        attachmentsSeen = {attachment}
                        for conflictIndex, conflict in enumerate(conflicts):
                            if conflict in attachmentsSeen:
                                printWarning(f'duplicate attachment ID (attachmentConflicts.{category}.{attachment}[{conflictIndex}])')
                            else:
                                checkAttachmentName(category, conflict, f'attachmentConflicts.{category}.{attachment}[{conflictIndex}]')
                                frozenDuo = frozenset({attachment, conflict})
                                categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                                if debug:
                                    logSkip(frozenDuo, category=category)
                                attachmentsSeen.add(conflict)

                if debug:
                    sprintPad()
                    sprint('Reading equivalentParts...')

                categoryComboEquivalentMap = {}
                for category, equivalentCombosMap in equivalentParts.items():
                    if category not in categoryComboEquivalentMap:
                        categoryComboEquivalentMap[category] = {}

                    comboEquivalentMap = categoryComboEquivalentMap[category]

                    for equivalent, groups in equivalentCombosMap.items():
                        checkAttachmentName(category, equivalent, 'equivalentParts->equivalent')
                        for groupIndex, parts in enumerate(groups):
                            frozenParts = frozenset(parts)
                            if frozenParts in comboEquivalentMap:
                                printWarning(f'duplicate group (equivalentParts.{category}.{equivalent}[{groupIndex}])')
                                continue

                            # TODO: allow group to map to multiple equivalents?
                            comboEquivalentMap[frozenParts] = equivalent

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            partsSeen = set()
                            for partIndex, part in enumerate(parts):
                                if part in partsSeen:
                                    printWarning(f'duplicate part (equivalentParts.{equivalent}[{groupIndex}][{partIndex}])')
                                else:
                                    checkAttachmentName(category, part, f'equivalentParts.{equivalent}[{groupIndex}][{partIndex}]')
                                    for comboToSkip, baseModels in [(k, v) for k, v in categoryCombinationSubsetsToSkip[category].items()]:
                                        if part in comboToSkip and not frozenParts <= comboToSkip:
                                            # if we would skip some of an aggregate's parts (but not all) when combined with attachments A,
                                            # skip attachments A when combined with the aggregate.
                                            newCombo = set(comboToSkip)
                                            newCombo.remove(part)
                                            newCombo.add(equivalent)
                                            if len(newCombo) > 1:
                                                frozenCombo = frozenset(newCombo)
                                                categoryCombinationSubsetsToSkip[category][frozenCombo] = baseModels
                                                if debug:
                                                    logSkip(frozenCombo, baseModels, category=category)

                                    # don't allow combos that contain both an attachment and one or more of its parts
                                    frozenCombo = frozenset({equivalent, part})
                                    categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                                    if debug:
                                        logSkip(frozenCombo, category=category)
                                    partsSeen.add(part)

                if debug:
                    sprintPad()
                    sprint('Reading supersetParts...')

                for category, attachmentProperSubsetsMap in supersetParts.items():
                    for attachment, properSubsets in attachmentProperSubsetsMap.items():
                        checkAttachmentName(category, attachment, f'supersetParts->superset')
                        for groupIndex, parts in enumerate(properSubsets):
                            properSubset = frozenset(parts)

                            if True:
                                if categoryComboEquivalentMap.get(category, {}).get(properSubset, None) == attachment:
                                    printWarning(f"proper subset ({properSubset}) is also a perfect subset of {attachment}")
                                    continue

                            if category not in categoryCombinationSubsetsToSkip:
                                categoryCombinationSubsetsToSkip[category] = {}

                            for partIndex, part in enumerate(parts):
                                checkAttachmentName(category, part, f'supersetParts.{attachment}[{groupIndex}][{partIndex}]')
                                for comboToSkip, baseModels in [(k, v) for k, v in categoryCombinationSubsetsToSkip[category].items()]:
                                    if part in comboToSkip:
                                        # if we would skip a subset part when combined with other attachments,
                                        # skip the same other attachments when combined with the superset attachment
                                        newCombo = set(comboToSkip)
                                        newCombo.remove(part)
                                        newCombo.add(attachment)
                                        if len(newCombo) > 1:
                                            frozenCombo = frozenset(newCombo)
                                            categoryCombinationSubsetsToSkip[category][frozenCombo] = baseModels
                                            if debug:
                                                logSkip(frozenCombo, baseModels, category=category, info=f"{attachment} ⊃ {part}...{','.join(comboToSkip)}")

                                # don't allow combos that contain both an attachment and one or more of its proper subset parts
                                frozenCombo = frozenset({attachment, part})
                                categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                                if debug:
                                    logSkip(frozenCombo, category=category)

                if debug:
                    sprintPad()
                    sprint('Excluding equivalent combos...')

                for category, comboEquivalentMap in categoryComboEquivalentMap.items():
                    if category not in categoryCombinationSubsetsToSkip:
                        categoryCombinationSubsetsToSkip[category] = {}

                    for frozenCombo in comboEquivalentMap.keys():
                        # don't allow combos containing all the parts of an entire equivalent attachment - use the equivalent instead
                        categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                        if debug:
                            logSkip(frozenCombo, category=category)

                sprintPad()
                sprint('Exclusion rules generated.')
                sprintPad()

                if debug:
                    sprintPad()
                    sprint('categoryCombinationSubsetsToSkip:')
                    sprintPad()
                    sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationSubsetsToSkip))}')
                    sprintPad()
                    sprint('categoryCombinationsToSkip:')
                    sprintPad()
                    sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationsToSkip))}')
                    sprintPad()

        if (inspecting or extractingAttachments or mixingAttachments) and customizationItemDb is not None:
            exports = customizationItemDb['Exports']
            dataTableExport = findNextItemByType(exports, 'UAssetAPI.ExportTypes.DataTableExport, UAssetAPI')
            models = dataTableExport['Table']['Data']
            modelsCopy = models.copy()
            if mixingAttachments:
                models.clear()
            sprintPad()
            sprint(f'Reading {len(modelsCopy)} models...')
            for modelIndex, model in enumerate(modelsCopy):
                try:
                    modelName = getModelName(model)
                    sprintPad()
                    sprint(f'{modelIndex + 1} - reading {modelName}...')

                    modelValues = getPropertyValue(model)

                    modelIdProp = getModelIdProperty(modelValues)
                    modelId = getPropertyValue(modelIdProp)
                    if modelId != modelName:
                        printWarning(f'ID ({modelId}) does not match model name ({modelName})')

                    modelNameParts = modelName.split('_')
                    modelBaseName = modelNameParts.pop(0)
                    sprint(f'Base Name: {modelBaseName}')

                    uiDataValues = getUiDataValues(modelValues)

                    modelDisplayNameProp = getModelDisplayNameProperty(uiDataValues)
                    modelDisplayName = modelDisplayNameProp[ModelDisplayNamePropNameFieldName]
                    sprint(f"Display Name: {modelDisplayName or '(none)'}")

                    categoryEnum = findEnumByType(modelValues, ECustomizationCategoryName)
                    categoryFullName = getEnumValue(categoryEnum)

                    categoryName = categoryFullName[len(ECustomizationCategoryNamePrefix):]
                    shortCategoryName = None
                    if categoryName == 'SurvivorTorso':
                        shortCategoryName = 'Torso'
                    elif categoryName == f'SurvivorLegs':
                        shortCategoryName = 'Legs'
                    elif categoryName == f'SurvivorHead':
                        shortCategoryName = 'Head'
                    else:
                        raise ValueError(f'Unsupported customization category: {categoryFullName}')

                    sprint(f'Category: {categoryName}')

                    socketAttachments = getSocketAttachments(modelValues)
                    sprint(f'Attachments: {len(socketAttachments)}')

                    if len(socketAttachments):
                        # TODO: ignore this - it's not a reliable way of determining attachment names
                        otherNames = [n for n in modelNameParts if n.lower() not in {'torso', 'legs', 'head', 'body', 'weapon', 'outfits', 'charm'}]
                        otherNamesString = '_'.join(otherNames)
                        attachmentNames = otherNamesString.split(importAttachmentsSeparator) if otherNamesString else []

                        if debug:
                            sprint(f"Potential attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        attachmentDisplayNamesString = ''
                        openParenIndex = modelDisplayName.find('(')
                        if openParenIndex > -1:
                            closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                            if closeParenIndex > -1:
                                attachmentDisplayNamesString = modelDisplayName[(openParenIndex + 1):closeParenIndex]

                        if debug:
                            sprint(f'Potential attachments display names string: {attachmentDisplayNamesString}')

                        attachmentDisplayNames = attachmentDisplayNamesString.split(', ') if attachmentDisplayNamesString else []
                        if debug:
                            sprint(f"Potential attachments display names: {', '.join(attachmentDisplayNames) if attachmentDisplayNames else '(unknown)'}")

                        if (
                            len(attachmentDisplayNames) == len(socketAttachments)
                            or (len(attachmentDisplayNames) > 1 and len(socketAttachments) == 1)
                        ):
                            attachmentNames = [''.join([word.capitalize() for word in displayName.split()]) for displayName in attachmentDisplayNames]
                            # TODO: try to handle cases with aggregate attachments?
                            if len(attachmentDisplayNames) > 1 and len(socketAttachments) == 1:
                                attachmentNames = ['And'.join(attachmentNames)]
                                attachmentDisplayNames = [', '.join(attachmentDisplayNames)]

                        if len(attachmentNames) != len(socketAttachments):
                            attachmentNames = []

                        if len(attachmentDisplayNames) != len(socketAttachments):
                            attachmentDisplayNames = []

                        if debug:
                            sprint(f"Synthesized attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        if extractingAttachments:
                            for attachmentIndex, attachmentData in enumerate(socketAttachments):
                                if attachmentIndex < len(attachmentNames):
                                    attachmentId = attachmentNames[attachmentIndex]
                                elif otherNamesString:
                                    attachmentId = f'{otherNamesString}_{attachmentIndex}'
                                else:
                                    attachmentId = f'{modelIndex}_{attachmentIndex}'

                                if attachmentIndex < len(attachmentDisplayNames):
                                    attachmentDisplayName = attachmentDisplayNames[attachmentIndex]
                                else:
                                    attachmentDisplayName = f'{otherNamesString}_{attachmentIndex}'

                                filename = f'SocketAttachment_{modelBaseName}_{shortCategoryName}_{attachmentId}.yaml'
                                filePath = getPathInfo(os.path.join(ensureAttachmentsDir(), filename))['best']

                                if os.path.exists(filePath):
                                    printWarning(f'Skipping attachment {attachmentIndex + 1} (file already exists): "{filePath}"', pad=False)
                                else:
                                    sprint(f'{dryRunPrefix}Exporting attachment {attachmentIndex + 1}: {attachmentId} ({attachmentDisplayName}) to "{filePath}"')

                                    attachmentInfo = {
                                        'attachmentId': attachmentId,
                                        'modelCategory': categoryName,
                                        'displayName': attachmentDisplayName,
                                        'attachmentData': attachmentData,
                                    }

                                    if not dryRun:
                                        with open(filePath, 'w') as file:
                                            yamlDump(attachmentInfo, file)

                                    attachmentsCreated.append(filePath)
                    elif mixingAttachments:
                        models.append(model)
                        if categoryName in attachmentsToMix:
                            modelDisplayNameBase = modelDisplayName
                            openParenIndex = modelDisplayName.find('(')
                            if openParenIndex > -1:
                                closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                                if closeParenIndex > -1:
                                    modelDisplayNameBase = modelDisplayName[:openParenIndex].rstrip()

                            comboCount = 0

                            attachmentsForCategory = attachmentsToMix[categoryName]
                            sprintPad()
                            sprint(f'Mixing {len(attachmentsForCategory)} attachments into combinations...')
                            sprintPad()
                            for r in range(1, len(attachmentsForCategory) + 1):
                                # TODO: use names instead of values in combinations()
                                for combo in combinations(attachmentsForCategory.values(), r):
                                    attachmentIds = [a['attachmentId'] for a in combo]

                                    attachmentIdsSet = frozenset(attachmentIds)

                                    shouldSkipCombo = False
                                    if not shouldSkipCombo:
                                        baseModels = categoryCombinationsToSkip.get(categoryName, {}).get(attachmentIdsSet, None)
                                        if baseModels is not None:
                                            if len(baseModels) == 0 or modelBaseName in baseModels:
                                                shouldSkipCombo = True

                                    if not shouldSkipCombo:
                                        for combosToSkip, baseModels in categoryCombinationSubsetsToSkip.get(categoryName, {}).items():
                                            if (len(baseModels) == 0 or modelBaseName in baseModels) and combosToSkip <= attachmentIdsSet:
                                                shouldSkipCombo = True
                                                break

                                    if shouldSkipCombo:
                                        if modelBaseName not in combinationsSkipped:
                                            combinationsSkipped[modelBaseName] = {}
                                        if categoryName not in combinationsSkipped[modelBaseName]:
                                            combinationsSkipped[modelBaseName][categoryName] = set()
                                        combinationsSkipped[modelBaseName][categoryName].add(attachmentIdsSet)
                                        continue

                                    if modelBaseName not in combinationsAdded:
                                        combinationsAdded[modelBaseName] = {}
                                    if categoryName not in combinationsAdded[modelBaseName]:
                                        combinationsAdded[modelBaseName][categoryName] = set()
                                    combinationsAdded[modelBaseName][categoryName].add(attachmentIdsSet)
                                    comboCount += 1

                                    attachmentNamesString = exportAttachmentsSeparator.join(attachmentIds)
                                    attachmentDisplayNamesString = ', '.join([getAttachmentDisplayName(a) for a in combo])
                                    newModelDisplayName = f'{modelDisplayNameBase} ({attachmentDisplayNamesString})'
                                    if True:
                                        attachmentNamesHashed = md5Hash(attachmentNamesString).upper()
                                        newModelId = f'{modelBaseName}_{shortCategoryName}_{attachmentNamesHashed}'
                                    else:
                                        # TODO: use UUID instead?
                                        newModelId = f'{modelBaseName}_{shortCategoryName}_{attachmentNamesString}'
                                    # TODO: warn if this ID has already been used
                                    sprint(f"Making combo: {', '.join(attachmentIds)}")
                                    newModel = copy.deepcopy(model)
                                    newModelValues = getPropertyValue(newModel)
                                    newModelIdProp = getModelIdProperty(newModelValues)
                                    setPropertyValue(newModelIdProp, newModelId)
                                    setModelName(newModel, newModelId)

                                    newUiDataValues = getUiDataValues(newModelValues)

                                    newModelDisplayNameProp = getModelDisplayNameProperty(newUiDataValues)
                                    newModelDisplayNameProp[ModelDisplayNamePropNameFieldName] = newModelDisplayName

                                    if False:
                                        newModelDisplayNameProp[ValueFieldName] = generateRandomHexString(32).upper()
                                    elif False:
                                        # TODO: use same algorithm unreal engine uses - this is not identical, but it seems to do the trick anyway
                                        newModelDisplayNameProp[ValueFieldName] = sha256Hash(newModelDisplayName.lower()).upper()
                                    else:
                                        newModelDisplayNameProp[ValueFieldName] = md5Hash(newModelDisplayName.lower()).upper()

                                    newSocketAttachmentsStruct = findSocketAttachmentsStruct(newModelValues)
                                    newSocketAttachmentsStruct.pop('DummyStruct', None)
                                    newSocketAttachments = getPropertyValue(newSocketAttachmentsStruct)

                                    for attachment in combo:
                                        newSocketAttachments.append(attachment['attachmentData'])
                                        # TODO: remove
                                        if False:
                                            addAllToNameMap(attachment['attachmentData'], nameMapSet)

                                    # TODO: alter model icons and descriptions if specified

                                    models.append(newModel)
                                    # TODO: remove
                                    if False:
                                        nameMapSet.add(newModelId)
                            sprint(f'Created {comboCount} combos')
                            sprintPad()
                except Exception as e:
                    printError(e)

            sprintPad()
            sprint('Models processed.')
            sprintPad()

            if mixingAttachments and customizationItemDb is not None:
                nameMapArrayCopy = nameMapArray.copy()
                nameMapArray.clear()
                nameMapSet.clear()
                addAllToNameMap(customizationItemDb.get('Imports', []), nameMapSet)
                addAllToNameMap(customizationItemDb.get('Exports', []), nameMapSet)

                if True:
                    # could other names be required?
                    for name in {
                        'EnumProperty',
                        'TextProperty',
                        'ObjectProperty',
                        'BoolProperty',
                        'UInt32Property',
                        'MapProperty',
                        'IntProperty',
                        'ArrayProperty',
                    }:
                        nameMapSet.add(name)

                # TODO: remove? doesn't seem to be required
                if False:
                    customizationItemDbName = next((name for name in nameMapArrayCopy if name.startswith('/Game/Data/Dlc/') and name.endswith(f'/{CustomizationItemDbAssetName}')), None)
                    if customizationItemDbName:
                        nameMapSet.add(customizationItemDbName)

                for name in nameMapSet:
                    nameMapArray.append(name)
                nameMapArray.sort(key=lambda v: v.upper())

                nameMapSetOld = set(nameMapArrayCopy)

                nameMapNamesRemoved = nameMapSetOld - nameMapSet
                nameMapNamesAdded = nameMapSet - nameMapSetOld

                if debug:
                    sprintPad()
                    sprint(f'NameMap names removed:')
                    sprint(yamlDump(jsonifyDataRecursive(nameMapNamesRemoved)))
                    sprintPad()

                if debug:
                    sprintPad()
                    sprint(f'NameMap names added:')
                    sprint(yamlDump(jsonifyDataRecursive(nameMapNamesAdded)))
                    sprintPad()

                if writingAlteredDb:
                    jsonOutPath = getPathInfo(os.path.join(
                        settingsDir,
                        f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.json",
                    ))['best']
                    sprintPad()
                    sprint(f'{dryRunPrefix}Writing altered {CustomizationItemDbAssetName} to "{jsonOutPath}"')
                    shouldWrite = not dryRun
                    written = False
                    if shouldWrite:
                        if readyToWrite(jsonOutPath, overwrite=True, dryRunHere=False):
                            with open(jsonOutPath, 'w') as file:
                                jsonDump(customizationItemDb, file)
                                written = True
                    if written or dryRun:
                        sprint(f'{dryRunPrefix if not written else ""}Done writing.')
                    sprintPad()

                    if customizationItemDbPathInfo['suffixLower'] == '.uasset':
                        sprintPad()
                        sprint(f'{dryRunPrefix}Writing altered {CustomizationItemDbAssetName} to "{customizationItemDbPath}"')
                        if os.path.exists(uassetGuiPath):
                            shouldWrite = not dryRun
                            written = False
                            if shouldWrite:
                                if readyToWrite(customizationItemDbPath, dryRunHere=False):
                                    jsonToUasset(jsonOutPath, customizationItemDbPath, uassetGuiPath)
                                    written = True
                            if written or dryRun:
                                sprint(f'{dryRunPrefix if not written else ""}Done writing.')
                            sprintPad()
                        else:
                            printError(f'`uassetGuiPath` ("{uassetGuiPath})" does not exist')

                    # TODO: this should be optional
                    if True:
                        yamlOutPath = getPathInfo(os.path.join(
                            settingsDir,
                            f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.yaml",
                        ))['best']
                        sprintPad()
                        sprint(f'{dryRunPrefix}Writing altered {CustomizationItemDbAssetName} to "{yamlOutPath}"')
                        shouldWrite = not dryRun
                        written = False
                        if shouldWrite:
                            if readyToWrite(yamlOutPath, overwrite=True, dryRunHere=False):
                                with open(yamlOutPath, 'w') as file:
                                    yamlDump(customizationItemDb, file)
                                    written = True
                        if written or dryRun:
                            sprint(f'{dryRunPrefix if not written else ""}Done writing.')
                        sprintPad()

        if paking or inspecting:
            sprintPad()
            sprint(f'Analyzing target pak configuration...')
            if destPakNumber >= 0 or destPakName or destPakAssets is not None or srcPakNumber >= 0:
                if destPakNumber < 0 and srcPakNumber >= 0:
                    destPakNumber = srcPakNumber
                    printWarning(f'Setting `destPakNumber` to "{destPakNumber}" from `srcPakPath`')
                    if srcPakName != destPakName:
                        destPakName = srcPakName
                        printWarning(f'Setting `destPakName` to "{destPakName}" from `srcPakPath`')

                if destPakNumber < 0 and paking:
                    printError('Missing or invalid `destPakNumber`')

                if destPakNumber >= 0:
                    destPakStem = pakchunkRefnamePartsToRefname(
                        destPakNumber,
                        destPakName,
                        destPlatform,
                        destPakPlatformSuffix,
                        addSuffix=False,
                    )
                    destPakDir = getPathInfo(os.path.join(ensurePakingDir(), destPakStem))['best']

                    sprintPad()
                    sprint(f'Destination pak: "{destPakDir}"')
                    sprintPad()

                    if gameName:
                        destPakContentDir = getPakContentDir(destPakDir, gameName)
                    else:
                        message = f'Cannot resolve destination pak content folder (missing `gameName`)'
                        if paking:
                            printError(message)
                        else:
                            printWarning(message)

                    destPakFilename = f'{destPakStem}{PakchunkFilenameSuffix}'
                    destPakPath = getPathInfo(os.path.join(ensurePakingDir(), destPakFilename))['best']

                if not destPakAssets:
                    printWarning(f'Zero assets configured for paking (empty `destPakAssets`)')

                if srcPakPath:
                    srcAssetPathMap = srcPakContentAssetPathsMap
                    srcContentDir = srcPakContentDir
                elif unrealProjectDir:
                    srcAssetPathMap = cookedContentAssetPathsMap
                    srcContentDir = cookedContentDir
                else:
                    srcAssetPathMap = {}
                    srcContentDir = ''

                shouldSearchForSrcAssets = True

                if not srcContentDir:
                    message = f'Missing source content folder for paking'
                    if paking:
                        printError(message)
                        shouldSearchForSrcAssets = False
                    else:
                        printWarning(message)

                if shouldSearchForSrcAssets:
                    sprintPad()
                    sprint(f'Searching "{srcContentDir}" for {len(destPakAssets)} assets to pak')

                    srcAssetCount = 0
                    srcFileCount = 0

                    missingAssets = False
                    for asset in destPakAssets:
                        if asset not in srcAssetPathMap:
                            missingAssets = True
                            message = f'Missing "{asset}" from "{srcContentDir}"'
                            if paking:
                                printError(message)
                            else:
                                printWarning(message)
                        else:
                            srcAssetCount += 1
                            srcFileCount += len(srcAssetPathMap[asset])

                    sprintPad()
                    sprint(f'Found {srcAssetCount} assets ({srcFileCount} files).')
                    sprintPad()

                    if paking and not missingAssets:
                        if not destPakContentDir:
                            printError(f'Cannot create pak because destination content folder is missing')
                        else:
                            assert destPakDir
                            sprintPad()
                            sprint(f'{dryRunPrefix}Copying {srcFileCount} files from "{srcContentDir}" to "{destPakContentDir}"')
                            ensurePakingDir()
                            sameDir = srcPakDir == destPakDir
                            if sameDir:
                                printWarning(f'Source and destination pak folder is the same. {dryRunPrefix}Files not in asset list will be removed.')
                            if readyToWrite(destPakDir, delete=not sameDir):
                                def writeFiles(srcContentDir):
                                    ensureDir(destPakContentDir, warnIfNotExist=False)
                                    for assetPath in destPakAssets:
                                        for extension in srcAssetPathMap[assetPath]:
                                            relFilePath = f'{assetPath}{extension}'
                                            srcPath = normPath(os.path.join(srcContentDir, relFilePath))
                                            destPathFileInfo = getPathInfo(os.path.join(destPakContentDir, relFilePath))
                                            ensureDir(destPathFileInfo['dir'], warnIfNotExist=False)
                                            destPath = destPathFileInfo['best']
                                            sprint(f'{dryRunPrefix}Copying file to "{destPath}"')
                                            if not dryRun:
                                                shutil.copy(srcPath, destPath)
                                if sameDir:
                                    with tempfile.TemporaryDirectory(
                                        dir=pakingDir,
                                        prefix=f'{destPakStem}_',
                                    ) as tempDir:
                                        printWarning(f'{dryRunPrefix}Temporarily moving "{srcPakDir}" to temporary source pak folder ("{tempDir}") for file copying')
                                        if not dryRun:
                                            os.rmdir(tempDir)
                                            shutil.move(srcPakDir, tempDir)
                                        assert gameName
                                        try:
                                            writeFiles(getPakContentDir(tempDir, gameName))
                                        except Exception as e:
                                            if not nonInteractive and debug:
                                                printError(e)
                                                promptToContinue(f'to open src content dir "{tempDir}"')
                                                openFolder(tempDir)
                                                promptToContinue()
                                            raise e
                                else:
                                    writeFiles(srcContentDir)

                                assert destPakPath
                                sprintPad()
                                sprint(f'{dryRunPrefix}Paking "{destPakDir}" into "{destPakPath}"')
                                if os.path.exists(unrealPakPath):
                                    if not dryRun:
                                        unrealPak(destPakDir, destPakPath, unrealPakPath)
                                    sprint(f'{dryRunPrefix}Done paking.')
                                else:
                                    printError(f'`unrealPakPath` ("{unrealPakPath})" does not exist')
                                sprintPad()
        if installingMods or inspecting:
            sprintPad()
            sprint(f'Analyzing mod configuration...')
            sprintPad()
            sprint(f'Resolving game Paks folder...')

            # don't do the install if there are errors configuring mods
            skipInstall = False

            if not gameDir:
                message = f'Cannot resolve game Paks folder (missing or invalid `gameDir`)'
                skipInstall = True
                if installingMods:
                    printError(message)
                else:
                    printWarning(message)

            if not gameName:
                message = f'Cannot resolve game Paks folder (missing `gameName`)'
                skipInstall = True
                if installingMods:
                    printError(message)
                else:
                    printWarning(message)

            reservedPakchunksFilenameLower = []
            for refI, pakchunkRefname in enumerate(reservedPakchunks):
                fullFilename = pakchunkRefnameToFilename(pakchunkRefname)
                if not fullFilename:
                    printError(f'`reservedPakchunks[{refI}] is not a valid pakchunk reference ("{pakchunkRefname})')
                    skipInstall = True
                else:
                    if debug and fullFilename.lower() != pakchunkRefname.lower():
                        sprint(f'Resolved reserved pakchunk reference from "{pakchunkRefname}" to "{fullFilename}"')
                    reservedPakchunksFilenameLower.append(fullFilename.lower())

            if gameDir and gameName:
                gamePaksDir = getGamePaksDir(gameDir, gameName)
                sprint(f'Resolved.')
                sprintPad()
                if not os.path.isdir(gamePaksDir):
                    printError(f'Game paks folder does not exist ("{gamePaksDir}")')
                else:
                    sprint(f'Scanning "{gamePaksDir}" for pakchunk files...')
                    allPakchunks = []
                    loggingReserved = debug
                    for relPath in listFilesRecursively(gamePaksDir):
                        relPathInfo = getPathInfo(relPath, gamePaksDir)
                        pakchunkFilenameParts = pakchunkRefnameToParts(relPathInfo['basename'])
                        if pakchunkFilenameParts:
                            allPakchunks.append(relPath)
                            reserved = relPath.lower() in reservedPakchunksFilenameLower
                            if not reserved:
                                stem = pakchunkRefnamePartsDictToRefname(pakchunkFilenameParts, addSuffix=False)
                                relStemPath = getPathInfo(os.path.join(relPathInfo['relativeDir'], stem), gamePaksDir)['relative']
                                gamePakchunks.append(relStemPath)
                            if not reserved or loggingReserved:
                                sprint(f'{len(allPakchunks if loggingReserved else gamePakchunks)} - {relPath}{" -- RESERVED" if reserved else ""}')
                        else:
                            printWarning(f'Non-pakchunk file discovered in Paks folder: "{relPath}"')
                    sprint('Done.')
                    sprintPad()
                    sprint(f'Discovered {len(allPakchunks)} pakchunks ({len(allPakchunks) - len(gamePakchunks)} reserved, {len(gamePakchunks)} swappable)')

            sprintPad()
            sprint(f'Scanning "{pakingDir}" for available pakchunks...')
            ensurePakingDir()
            for entry in os.scandir(pakingDir):
                pakchunkFilenameParts = pakchunkRefnameToParts(entry.name)
                if pakchunkFilenameParts and pakchunkFilenameParts.get('suffix', None):
                    stem = pakchunkRefnamePartsDictToRefname(pakchunkFilenameParts, addSuffix=False)
                    if stem not in pakingDirPakchunkStems:
                        pakingDirPakchunkStems.append(stem)
                        sprint(f'{len(pakingDirPakchunkStems)} - {stem}')
            sprint(f'Discovered {len(pakingDirPakchunkStems)} pakchunks.')
            sprintPad()
            sprint(f'Determining target active mod set...')

            if activeModConfigName:
                sprintPad()
                sprint(f'Active config: "{activeModConfigName}"')
                if activeModConfigName not in modConfigNameGroupsMap:
                    printError(f'Mod config "{activeModConfigName}" not found in `modConfigs`')
                    skipInstall = True
                else:
                    for groupName in modConfigNameGroupsMap[activeModConfigName]:
                        if groupName not in modGroupNamePakchunksMap:
                            printError(f'Mod group "{groupName}" not found in `modGroups`')
                            skipInstall = True
                        else:
                            for pakchunkIndex, pakchunkRefname in enumerate(modGroupNamePakchunksMap[groupName]):
                                pakchunkStem = pakchunkRefnameToFilename(pakchunkRefname, defaultPlatform=destPlatform, addSuffix=False)
                                modConfigPath = f'groups.{groupName}[{pakchunkIndex}]: {pakchunkStem}'
                                if pakchunkStem in targetActiveMods:
                                    printWarning(f'Already added mod to be active: {modConfigPath}')
                                else:
                                    targetActiveMods.append(pakchunkStem)
                                    sprint(f'{len(targetActiveMods)} - {modConfigPath}')
                sprintPad()

            sprint(f'Target active mods: {len(targetActiveMods)}.')
            sprintPad()

            sprintPad()
            sprint(f'Locating pakchunk sources...')
            if not gamePaksDir:
                if installingMods:
                    printError('Could not resolve game Paks folder')

            if gamePaksDir:
                notFoundPakchunks = []
                pakchunkSourceMap = {}
                gamePakchunkStemRelPathMap = {}
                for relStemPath in gamePakchunks:
                    pakchunkStem = os.path.basename(relStemPath)
                    gamePakchunkStemRelPathMap[pakchunkStem] = relStemPath

                for relStemPath in targetActiveMods:
                    pakchunkStem = os.path.basename(relStemPath)
                    if pakchunkStem in pakingDirPakchunkStems:
                        source = pakchunkSourceMap[relStemPath] = normPath(os.path.join(pakingDir, pakchunkStem))
                    elif pakchunkStem in gamePakchunkStemRelPathMap:
                        source = pakchunkSourceMap[relStemPath] = normPath(os.path.join(gamePaksDir, gamePakchunkStemRelPathMap[pakchunkStem]))
                    else:
                        printError(f'Pakchunk (to install) not found: {pakchunkStem}')
                        skipInstall = True
                        notFoundPakchunks.append(pakchunkStem)
                        source = None

                    if source is not None and debug:
                        sprint(f'"{relStemPath}" <- "{source}"')

                pakchunksToActivate = [p for p in targetActiveMods if p not in gamePakchunks]
                sprintPad()
                sprint(f'Pakchunks to activate: {len(pakchunksToActivate)}')
                for i, pakchunkRelStemPath in enumerate(pakchunksToActivate):
                    sprint(f'{i + 1} - {pakchunkRelStemPath}')

                pakchunksToDeactivate = [p for p in gamePakchunks if p not in targetActiveMods]
                sprintPad()
                sprint(f'Pakchunks to deactivate: {len(pakchunksToDeactivate)}')
                for i, pakchunkRelStemPath in enumerate(pakchunksToDeactivate):
                    sprint(f'{i + 1} - {pakchunkRelStemPath}')

                if not skipInstall and installingMods:
                    madeChanges = False

                    sprintPad()
                    sprint(f'{dryRunPrefix}Moving mods between "{pakingDir}" and "{gamePaksDir}"...')
                    for pakchunkRelStemPath in targetActiveMods:
                        source = f'{pakchunkSourceMap[pakchunkRelStemPath]}{PakchunkFilenameSuffix}'
                        pakchunkRelPath = f'{pakchunkRelStemPath}{PakchunkFilenameSuffix}'
                        dest = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                        if not os.path.exists(source):
                            printError(f'Mod to make active not found "{source}"')
                        elif not os.path.exists(dest) or not os.path.samefile(source, dest):
                            sprint(f'{dryRunPrefix}Moving "{source}" to "[Paks]/{pakchunkRelPath}"')
                            if readyToWrite(dest):
                                if not dryRun:
                                    shutil.move(source, dest)
                                madeChanges = True
                            else:
                                printWarning(f'Not allowed to overwrite "{pakchunkRelPath}"')

                    for pakchunkRelStemPath in pakchunksToDeactivate:
                        pakchunkStem = os.path.basename(pakchunkRelStemPath)
                        pakchunkFilename = f'{pakchunkStem}{PakchunkFilenameSuffix}'
                        pakchunkRelPath = f'{pakchunkRelStemPath}{PakchunkFilenameSuffix}'
                        source = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                        dest = normPath(os.path.join(pakingDir, pakchunkFilename))
                        if pakchunkStem in pakingDirPakchunkStems:
                            sprint(f'{dryRunPrefix}Removing "[Paks]/{pakchunkRelPath}" which is also stored at "{dest}"')
                            if readyToWrite(source):
                                if not dryRun:
                                    pathlib.Path.unlink(source)
                                madeChanges = True
                        else:
                            sprint(f'{dryRunPrefix}Moving "{pakchunkRelPath}" to "{dest}"')
                            if not dryRun:
                                shutil.move(source, dest)
                            madeChanges = True

                    sprint(f'{dryRunPrefix}Installation succeeded{"" if madeChanges else " - no changes made"}.')
                    sprintPad()
    except Exception as e:
        printError(e)

    if (
        inspecting
        or extractingAttachments
        or renamingAttachmentFiles
        or creatingAttachments
        or mixingAttachments
        or paking
        or installingMods
    ):
        outputInfo = {
            'warnings': warnings,
            'errors': errors,
            'discoveredSettingsFiles': discoveredSettingsFiles,
            'srcContentDir': srcContentDir,
            'destPakNumber': destPakNumber,
            'destPakName': destPakName,
            'destPlatform': destPlatform,
            'destPakDir': destPakDir,
            'destPakPath': destPakPath,
            'srcPakNumber': srcPakNumber,
            'srcPakName': srcPakName,
            'srcPakPlatform': srcPakPlatform,
            'srcPakContentDir': srcPakContentDir,
            'srcPakAssets': list(srcPakContentAssetPathsMap.keys()),
            'srcPakFiles': srcPakContentPaths,
            'attachmentsRead': {category: list(attachmentDataMap.keys()) for category, attachmentDataMap in attachmentsToMix.items()},
            'attachmentsRenamed': attachmentsRenamed,
            'attachmentsCreated': attachmentsCreated,
            'combosAdded': combinationsAdded,
            'combosSkipped': combinationsSkipped,
            'nameMapAlterations': {
                'namesRemoved': nameMapNamesRemoved,
                'namesAdded': nameMapNamesAdded,
            },
            'pakingDirPakchunks': pakingDirPakchunkStems,
            'gamePaksDir': gamePaksDir,
            'gamePakchunks': gamePakchunks,
            'targetActiveMods': targetActiveMods,
            'cookedContentDir': cookedContentDir,
            'cookedAssets': list(cookedContentAssetPathsMap.keys()),
            'cookedFiles': cookedContentPaths,
        }

        outputInfoFilename = getResultsFilePath(settingsFilePath)
        sprintPad()
        sprint(f'{dryRunPrefix}Writing command results to "{outputInfoFilename}"')
        shouldWrite = not dryRun or (not nonInteractive and confirm(f'write command results ("{outputInfoFilename}") despite dry run', pad=True, emptyMeansNo=True))
        written = False
        if shouldWrite:
            # TODO: should we not overwrite result file without confirmation?
            if readyToWrite(outputInfoFilename, overwrite=True):
                with open(outputInfoFilename, 'w') as file:
                    yamlDump(jsonifyDataRecursive(outputInfo), file)
                    written = True
        if written or dryRun:
            sprint(f'{dryRunPrefix if not written else ""}Done writing.')
        sprintPad()

    if openingGameLauncher:
        sprintPad()
        sprint(f'{dryRunPrefix}Opening game launcher{" and starting game if not already running" if launcherStartsGame else ""} (exit the launcher to return)...')
        if nonInteractive:
            printError('Cannot open game launcher in non-interactive mode')
        elif not gameDir:
            printError('Missing or invalid `gameDir`')
        elif not dryRun:
            warningOfLauncherClearScreen = launcherClearsScreenBuffer and not getSprintIsRecording()
            if (
                warningOfLauncherClearScreen
                and overwriteOverride is not True
                and (
                    inspecting
                    or extractingAttachments
                    or renamingAttachmentFiles
                    or creatingAttachments
                    or mixingAttachments
                    or paking
                    or installingMods
                )
            ):
                shouldProceed = confirm('open the launcher and clear the screen buffer history', pad=True, emptyMeansNo=False)
            else:
                shouldProceed = True

            if shouldProceed:
                try:
                    launcherExitCode = openGameLauncher(getPathInfo(gameDir)['best'], startGame=launcherStartsGame, fromMenu=fromMenu)
                    if launcherExitCode:
                        message = f'launcher returned exit code: {launcherExitCode}'
                        printError(message)

                    setConsoleTitle(ConsoleTitle)
                    # TODO: remove
                    if False:
                        # clear any last bits of the launcher output left over
                        sprintClear()
                    if launcherClearsScreenBuffer and getSprintIsRecording():
                        replaySprintRecording()
                except Exception as e:
                    printError(e)
                finally:
                    clearSprintRecording()
        sprintPad()

    return exitCode
