import copy
import json
import os
import pathlib
import shutil
import tempfile
from itertools import combinations

import yaml

from attachmentHelpers import (basicAttachmentTemplate,
                               getAttachmentDisplayName, getAttachmentFilename)
from consoleHelpers import (clearSprintRecording, confirm, confirmOverwrite,
                            esprint, getSprintIsRecording, oneLinePrinter,
                            promptToContinue, replaySprintRecording, sprint,
                            sprintPad, sprintput, startSprintRecording)
from customizationItemDbHelpers import (CustomizationItemDbAssetName,
                                        ECustomizationCategoryName,
                                        ECustomizationCategoryNamePrefix,
                                        ModelDisplayNamePropNameFieldName,
                                        addAllToNameMap,
                                        findSocketAttachmentsStruct,
                                        generateRandomHexString,
                                        getModelDisplayNameProperty,
                                        getModelIdProperty, getModelName,
                                        getSocketAttachments, getUiDataValues,
                                        md5Hash, setModelName, sha256Hash)
from fileHelpers import listFilesRecursively
from gameHelpers import (getGameIsRunning, getGamePaksDir, killGame,
                         openGameLauncher)
from jsonHelpers import jsonDump, jsonifyDataRecursive
from pakHelpers import (DefaultPlatform, PakchunkFileExtension,
                        getPackchunkFilenameParts, getPakContentDir,
                        toPakchunkStem, unrealPak, unrealUnpak)
from pathHelpers import getPathInfo, normPath
from settingsHelpers import (DefaultAttachmentsDir,
                             DefaultCustomizationItemDbPath, DefaultPakingDir,
                             DefaultUassetGuiPath, DefaultUnrealPakPath,
                             findSettingsFiles, getContentDirRelativePath,
                             getResultsFilePath, getSettingsTemplate)
from uassetHelpers import (ItemTypeName, NameFieldName, ValueFieldName,
                           findEnumByType, findNextItemByFields,
                           findNextItemByType, getEnumValue, getPropertyValue,
                           jsonToUasset, setPropertyValue, uassetToJson)
from unrealEngineHelpers import (UnrealEngineCookedSplitFileExtensions,
                                 getUnrealProjectCookedContentDir)
from windowsHelpers import openFolder
from yamlHelpers import yamlDump


def runCommand(**kwargs):
    """ Main entry point of the app """

    settingsFilePath = kwargs.get('settingsFilePath', '')
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
    overwriteOverride = kwargs.get('overwriteOverride', None)

    if openingGameLauncher:
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
    def printError(message, pad=True):
        nonlocal exitCode

        exitCode = 1

        errors.append(str(message))
        if pad:
            sprintPad()
        esprint(f'ERROR: {message}')
        if pad:
            sprintPad()

    if killingGame:
        sprintPad()
        sprint(f'Killing game...')
        if getGameIsRunning():
            killGame()
            sprint(f'Game process terminated.')
            # TODO: need to wait?
        else:
            sprint('Game is not running.')
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

    attachmentsDir = ''
    cookedContentDir = ''
    cookedContentPaths = []
    cookedContentAssetPathsMap = {}
    gameDir = ''
    gamePaksDir = ''
    gamePakchunks = []
    reservedPakchunks = []
    modsToBeActive = []
    pakingDirPakchunks = []
    gameName = ''
    unrealProjectDir = ''
    unrealPakPath = ''
    pakingDir = ''
    srcPakPath = ''
    srcPakStem = ''
    srcPakDir = ''
    srcPakNumber = None
    srcPakName = None
    srcPakPlatform = None
    srcContentDir = ''
    srcPakContentDir = ''
    srcPakContentPaths = []
    srcPakContentAssetPathsMap = {}
    destPakNumber = None
    destPakName = ''
    destPakAssets = None

    destPakStem = ''
    destPakDir = ''
    destPakContentDir = ''
    destPakPath = ''

    destPlatform = DefaultPlatform

    customizationItemDbPath = ''
    customizationItemDbJsonPath = ''
    customizationItemDb = None
    combinationsAdded = {}
    combinationsSkipped = {}
    attachmentsToMix = {}
    nameMapNamesRemoved = []
    nameMapNamesAdded = []
    attachmentsCreated = []
    nameMapArray = []
    nameMapSet = set(nameMapArray)
    attachmentsRenamed = {}

    def ensureDir(dir, title='Directory', warnIfNotExist=True):
        dir = getPathInfo(dir)['best']
        if not os.path.exists(dir):
            if warnIfNotExist:
                printWarning(f'{title or "Directory"} ("{dir}") does not exist. Creating it now.')
            os.makedirs(dir, exist_ok=True)
        return dir

    def ensureAttachmentsDir():
        return ensureDir(attachmentsDir, '`attachmentsDir`')

    def ensurePakingDir():
        return ensureDir(pakingDir, '`pakingDir`')

    def readyToWrite(path, delete=True, overwrite=None):
        path = getPathInfo(path)['best']

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
            result = confirmOverwrite(path)
            shouldWarn = False

        if shouldWarn:
            if result:
                printWarning(f'Overwriting "{path}"')
            else:
                printWarning(f'Skipping write of "{path}" (file exists)')

        if result and delete:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                pathlib.Path.unlink(path)

        return result

    def checkAttachmentName(category, attachmentName, otherInfo=None):
        if attachmentName not in attachmentsToMix.get(category, {}):
            printWarning(f"reference to missing attachment: {category}::{attachmentName}{' (' if otherInfo else ''}{otherInfo or ''}{')' if otherInfo else ''}")

    def mergeSettings(parentData, childData):
        for key, value in childData.items():
            # TODO: merge data instead of overwriting
            parentData[key] = childData[key]

    def readSettingsRecursive(filePath, relativeDir='.'):
        resultData = {}

        pathInfo = getPathInfo(filePath, relativeDir=relativeDir)
        filePath = pathInfo['best']

        sprint(f'Reading settings from "{filePath}"')
        if not os.path.isfile(filePath):
            raise ValueError(f'Could not read settings from "{filePath}" (file not found)')

        with open(filePath, 'r') as file:
            data = yaml.safe_load(file)

        # TODO: ensure relative paths in settings are converted to relative paths
        # to relativeDir

        for otherPath in data.get('import', []):
            # import paths are relative to the file importing them
            otherData = readSettingsRecursive(otherPath, relativeDir=pathInfo['dir'])
            mergeSettings(resultData, otherData)

        mergeSettings(resultData, data)

        return resultData

    try:
        if not os.path.exists(settingsFilePath):
            printWarning(f'Settings file ("{settingsFilePath}") does not exist. Creating it now with default content.')
            yamlStringContent = getSettingsTemplate()
            if printingYaml:
                sprint(yamlStringContent)
                sprintPad()
            with open(settingsFilePath, 'w') as file:
                file.write(yamlStringContent)

        settingsPathInfo = getPathInfo(settingsFilePath)
        settingsDir = settingsPathInfo['dir']
        settings = readSettingsRecursive(settingsFilePath)

        if not unrealPakPath:
            unrealPakPath = settings.get('unrealPakPath', None)
            usingDefault = unrealPakPath is None
            if usingDefault:
                unrealPakPath = DefaultUnrealPakPath
            unrealPakPath = getPathInfo(unrealPakPath)['best']
            if usingDefault and (
                inspecting
                or paking
                or (
                    srcPakPath and (
                        extractingAttachments
                        or mixingAttachments
                    )
                )
            ):
                printWarning(f'Missing or empty `unrealPakPath`. Defaulting to "{unrealPakPath}"')

        if not uassetGuiPath:
            uassetGuiPath = settings.get('uassetGuiPath', None)
            usingDefault = uassetGuiPath is None
            if usingDefault:
                uassetGuiPath = DefaultUassetGuiPath
            uassetGuiPath = getPathInfo(uassetGuiPath)['best']
            if usingDefault and (
                inspecting
                or (
                    customizationItemDbPath
                    and (
                        extractingAttachments
                        or mixingAttachments
                    )
                )
            ):
                printWarning(f'Missing or empty `uassetGuiPath`. Defaulting to "{uassetGuiPath}"')

        if not pakingDir:
            pakingDir = settings.get('pakingDir', None)
            usingDefault = pakingDir is None
            if usingDefault:
                pakingDir = DefaultPakingDir
            pakingDir = getPathInfo(pakingDir)['best']
            if usingDefault and (
                inspecting
                or extractingAttachments
                or mixingAttachments
                or paking
                or installingMods
            ):
                printWarning(f'Missing or empty `pakingDir`. Defaulting to "{pakingDir}"')

        if not attachmentsDir:
            attachmentsDir = settings.get('attachmentsDir', None)
            usingDefault = attachmentsDir is None
            if usingDefault:
                attachmentsDir = DefaultAttachmentsDir
            attachmentsDir = getPathInfo(attachmentsDir)['best']
            if usingDefault and (
                inspecting
                or extractingAttachments
                or creatingAttachments
                or renamingAttachmentFiles
                or mixingAttachments
            ):
                printWarning(f'Missing or empty `attachmentsDir`. Defaulting to "{attachmentsDir}"')

        if not gameDir:
            gameDir = getPathInfo(settings.get('gameDir', ''))['best']
            if not gameDir and inspecting:
                printWarning('Missing or empty `gameDir`')

        if not gameName:
            gameName = settings.get('gameName', '').strip()
            if not gameName and inspecting:
                printWarning('Missing or empty `gameName`')

        if not unrealProjectDir:
            unrealProjectDir = getPathInfo(settings.get('unrealProjectDir', ''))['best']
            if not unrealProjectDir and (
                inspecting
                or extractingAttachments
                or mixingAttachments
                or paking
            ):
                printWarning(f'Missing or empty `unrealProjectDir`')

        if not srcPakPath:
            srcPakPath = getPathInfo(settings.get('srcPakPath', ''))['best']
            if not srcPakPath and inspecting:
                printWarning(f'Missing or empty `srcPakPath`')

        if not customizationItemDbPath:
            customizationItemDbPath = getPathInfo(settings.get('customizationItemDbPath', ''))['best']
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
            destPakName = settings.get('destPakName', '').strip()
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
            elif not destPakAssets:
                if inspecting or paking:
                    printWarning('Empty `destPakAssets`')
            else:
                destPakAssets = [getPathInfo(p)['normalized'] for p in destPakAssets]

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

                    sprint(f'Writing to "{filePath}"')
                    if readyToWrite(filePath):
                        with open(filePath, 'w') as file:
                            yamlDump(attachment, file)
                        sprint('done.')

                    if not confirm('add another', emptyMeansNo=True):
                        done = True

                if canceled:
                    sprintPad()
                    sprint(f'Add canceled.')
                    sprintPad()

        if (inspecting or extractingAttachments or mixingAttachments or paking) and srcPakPath:
            sprintPad()
            sprint(f'Resolving source pak content directory...')
            if not gameName:
                printError(f'Cannot resolve source pak content directory (missing `gameName`)')
            else:
                if not os.path.exists(srcPakPath):
                    if not pathlib.Path(srcPakPath).suffix:
                        srcPakPath = f'{srcPakPath}{PakchunkFileExtension}'
                        printWarning(f'Trying `srcPakPath` with "{PakchunkFileExtension}" extension ("{srcPakPath})')

                if not os.path.exists(srcPakPath):
                    printError(f'`srcPakPath` ("{srcPakPath}") does not exist')
                elif os.path.isdir(srcPakPath):
                    srcPakDir = srcPakPath
                elif pathlib.Path(srcPakPath).suffix.lower() == PakchunkFileExtension:
                    srcPakPathInfo = getPathInfo(srcPakPath)
                    srcPakDir = getPathInfo(os.path.join(ensurePakingDir(), srcPakPathInfo['stem']))['best']
                    sprintPad()
                    sprint(f'Unpaking "{srcPakPath}" to "{srcPakDir}')
                    if os.path.exists(unrealPakPath):
                        ensurePakingDir()
                        if readyToWrite(srcPakDir):
                            unrealUnpak(srcPakPath, srcPakDir, gameName, unrealPakPath)
                        sprint('Done unpaking.')
                        sprintPad()
                    else:
                        printError(f'`unrealPakPath` ("{unrealPakPath})" does not exist')

                if srcPakDir:
                    srcPakPathInfo = getPathInfo(srcPakDir)
                    srcPakStem = srcPakPathInfo['stem']
                    srcPakFilenameParts = getPackchunkFilenameParts(srcPakStem)
                    if srcPakFilenameParts:
                        srcPakNumber = srcPakFilenameParts['number']
                        srcPakName = srcPakFilenameParts.get('name', '')
                        srcPakPlatform = srcPakFilenameParts.get('platform', '')
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
                        printError(f'Pak content directory ("{srcPakContentDir}") does not exist')
                        srcPakContentDir = ''

        if (inspecting or extractingAttachments or mixingAttachments or paking) and unrealProjectDir:
            if srcPakPath and not inspecting:
                printWarning(f'Not looking for unreal project cooked content because `srcPakDir` has precedence.')
            else:
                sprintPad()
                sprint(f'Resolving unreal project cooked content directory...')
                if not gameName:
                    printError(f'Cannot resolve unreal project cooked content directory (missing `gameName`)')
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
                        printError(f'Cooked content directory ("{cookedContentDir}") does not exist')
                        cookedContentDir = ''

        if inspecting or extractingAttachments or mixingAttachments:
            sprintPad()
            sprint(f'Resolving {CustomizationItemDbAssetName} path...')

            customizationItemDbPath = getPathInfo(settings.get('customizationItemDbPath', ''))['normalized']
            if not customizationItemDbPath:
                customizationItemDbPath = DefaultCustomizationItemDbPath
                printWarning(f'`customizationItemDbPath` not specified. Defaulting to: "{customizationItemDbPath}"')

            customizationItemDbContentDirRelativePath = getContentDirRelativePath(customizationItemDbPath)
            if customizationItemDbContentDirRelativePath is None:
                sprint(f'Resolved path: "{customizationItemDbPath}"')
            else:
                sprint(f'Content directory relative path detected: "{customizationItemDbPath}"')

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
                        message = 'Content directory relative path cannot be resolved because `srcPakPath` is missing content'
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
                        message = 'Content directory relative path cannot be resolved because `unrealProjectDir` is missing content'
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
                sprint(f'Converting "{customizationItemDbPath}" to JSON, writing "{customizationItemDbJsonPath}"')
                if os.path.exists(uassetGuiPath):
                    if readyToWrite(customizationItemDbJsonPath, overwrite=True):
                        uassetToJson(customizationItemDbPath, customizationItemDbJsonPath, uassetGuiPath)
                        sprint('Done converting.')
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
                    sprint(f'Writing unaltered {CustomizationItemDbAssetName} to "{outPath}"')
                    if readyToWrite(outPath, overwrite=True):
                        with open(outPath, 'w') as file:
                            yamlDump(customizationItemDb, file)
                    sprint(f'Done writing.')
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
                                    sprint(f'Renaming {filename} to {newFilename}')
                                    newFilePath = getPathInfo(os.path.join(ensureAttachmentsDir(), newFilename))['best']
                                    if os.path.exists(newFilePath):
                                        raise ValueError(f'Could not rename {filename} to {newFilename} (file already exists)')

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

                for category, combosList in settings.get('combosToSkip', {}).items():
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

                for category, groups in settings.get('mutuallyExclusive', {}).items():
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

                for category, attachmentConflictsMap in settings.get('attachmentConflicts', {}).items():
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
                for category, equivalentCombosMap in settings.get('equivalentParts', {}).items():
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

                for category, attachmentProperSubsetsMap in settings.get('supersetParts', {}).items():
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
                                attachmentDisplayNamesString = modelDisplayName[openParenIndex + 1:closeParenIndex]

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
                                    sprint(f'Exporting attachment {attachmentIndex + 1}: {attachmentId} ({attachmentDisplayName}) to "{filePath}"')

                                    attachmentInfo = {
                                        'attachmentId': attachmentId,
                                        'modelCategory': categoryName,
                                        'displayName': attachmentDisplayName,
                                        'attachmentData': attachmentData,
                                    }

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
                    sprint(f'Writing altered {CustomizationItemDbAssetName} to "{jsonOutPath}"')
                    if readyToWrite(jsonOutPath, overwrite=True):
                        with open(jsonOutPath, 'w') as file:
                            jsonDump(customizationItemDb, file)
                        sprint('Done.')
                    sprintPad()

                    if customizationItemDbPathInfo['suffixLower'] == '.uasset':
                        sprintPad()
                        sprint(f'Writing altered {CustomizationItemDbAssetName} to "{customizationItemDbPath}"')
                        if os.path.exists(uassetGuiPath):
                            if readyToWrite(customizationItemDbPath):
                                jsonToUasset(jsonOutPath, customizationItemDbPath, uassetGuiPath)
                                sprint('Done.')
                        else:
                            printError(f'`uassetGuiPath` ("{uassetGuiPath})" does not exist')
                        sprintPad()

                    # TODO: this should be optional
                    if True:
                        yamlOutPath = getPathInfo(os.path.join(
                            settingsDir,
                            f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.yaml",
                        ))['best']
                        sprintPad()
                        sprint(f'Writing altered {CustomizationItemDbAssetName} to "{yamlOutPath}"')
                        if readyToWrite(yamlOutPath, overwrite=True):
                            with open(yamlOutPath, 'w') as file:
                                yamlDump(customizationItemDb, file)
                            sprint('Done.')
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
                    destPakStem = toPakchunkStem(destPakNumber, destPakName, destPlatform)
                    destPakDir = getPathInfo(os.path.join(ensurePakingDir(), destPakStem))['best']

                    sprintPad()
                    sprint(f'Destination pak: "{destPakDir}"')
                    sprintPad()

                    if gameName:
                        destPakContentDir = getPakContentDir(destPakDir, gameName)
                    else:
                        message = f'Cannot resolve destination pak content directory (missing `gameName`)'
                        if paking:
                            printError(message)
                        else:
                            printWarning(message)

                    destPakFilename = f'{destPakStem}{PakchunkFileExtension}'
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
                    message = f'Missing source content directory for paking'
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
                            printError(f'Cannot create pak because destination content directory is missing')
                        else:
                            assert destPakDir
                            sprintPad()
                            sprint(f'Copying {srcFileCount} files from "{srcContentDir}" to "{destPakContentDir}"')
                            ensurePakingDir()
                            sameDir = srcPakDir == destPakDir
                            if sameDir:
                                printWarning(f'Source and destination pak directory is the same. Files not in asset list will be removed.')
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
                                            sprint(f'Copying file to "{destPath}"')
                                            shutil.copy(srcPath, destPath)

                                if sameDir:
                                    with tempfile.TemporaryDirectory(
                                        dir=pakingDir,
                                        prefix=f'{destPakStem}_',
                                    ) as tempDir:
                                        printWarning(f'Creating temporary source pak directory ("{tempDir}") for file copying')
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
                                sprint(f'Paking "{destPakDir}" into "{destPakPath}"')
                                if os.path.exists(unrealPakPath):
                                    unrealPak(destPakDir, destPakPath, unrealPakPath)
                                    sprint(f'Done paking.')
                                else:
                                    printError(f'`unrealPakPath` ("{unrealPakPath})" does not exist')
                                sprintPad()
        if installingMods or inspecting:
            sprintPad()
            sprint(f'Analyzing mod configuration...')
            sprintPad()
            sprint(f'Resolving game Paks directory path...')
            if not gameDir:
                message = f'Cannot resolve game Paks folder (missing `gameDir`)'
                if installingMods:
                    printError(message)
                else:
                    printWarning(message)

            if not gameName:
                message = f'Cannot resolve game Paks folder (missing `gameName`)'
                if installingMods:
                    printError(message)
                else:
                    printWarning(message)

            reservedPakchunks = [p.lower() for p in settings.get('reservedPakchunks', [])]
            if not reservedPakchunks:
                printWarning(f'Missing or empty `reservedPakchunks`')

            if gameDir and gameName:
                gamePaksDir = getGamePaksDir(gameDir, gameName)
                sprint(f'Resolved.')
                sprintPad()
                sprint(f'Scanning "{gamePaksDir}" for pakchunk files...')
                allPakchunks = []
                loggingReserved = debug
                for relPath in listFilesRecursively(gamePaksDir):
                    relPathPathInfo = getPathInfo(relPath, gamePaksDir)
                    if relPathPathInfo['basename'].lower().startswith('pakchunk'):
                        allPakchunks.append(relPath)
                        reserved = relPath.lower() in reservedPakchunks
                        if not reserved:
                            gamePakchunks.append(relPath)
                        if not reserved or loggingReserved:
                            sprint(f'{len(allPakchunks if loggingReserved else gamePakchunks)} - {relPath}{" -- RESERVED" if reserved else ""}')
                    else:
                        printWarning(f'Non-pakchunk file in Paks folder: "{relPath}"')
                sprint('Done.')
                sprintPad()
                sprint(f'Discovered {len(allPakchunks)} pakchunks ({len(allPakchunks) - len(gamePakchunks)} reserved, {len(gamePakchunks)} configurable)')

            sprintPad()
            sprint(f'Scanning "{pakingDir}" for available pakchunks...')
            ensurePakingDir()
            for entry in os.scandir(pakingDir):
                if entry.name.lower().startswith('pakchunk') and entry.name.lower().endswith(PakchunkFileExtension):
                    if entry.name not in pakingDirPakchunks:
                        pakingDirPakchunks.append(entry.name)
                        sprint(f'{len(pakingDirPakchunks)} - {entry.name}')
            sprint('Done.')
            sprintPad()
            sprint(f'Discovered {len(pakingDirPakchunks)} pakchunks.')
            sprintPad()
            sprint(f'Calculating mods to be active...')

            modGroupNamePakchunksMap = settings.get('modGroups', {})
            modConfigNameGroupsMap = settings.get('modConfigs', {})
            activeModConfigName = settings.get('activeModProfile', '')

            hasError = False
            if not activeModConfigName:
                printWarning('No active mod config (missing `activeModProfile`)')
            else:
                sprintPad()
                sprint(f'Active config: "{activeModConfigName}"')
                if activeModConfigName not in modConfigNameGroupsMap:
                    printError(f'Missing mod config "{activeModConfigName}" in `modConfigs`')
                    hasError = True
                else:
                    for groupName in modConfigNameGroupsMap[activeModConfigName]:
                        if groupName not in modGroupNamePakchunksMap:
                            printError(f'Missing mod group "{groupName}" in `modGroups`')
                            hasError = True
                        else:
                            for pakchunkIndex, pakchunk in enumerate(modGroupNamePakchunksMap[groupName]):
                                modConfigPath = f'groups.{groupName}[{pakchunkIndex + 1}]: {pakchunk}'
                                if pakchunk in modsToBeActive:
                                    printWarning(f'Already added mod to be active: {modConfigPath}')
                                else:
                                    modsToBeActive.append(pakchunk)
                                    sprint(f'{len(modsToBeActive)} - {modConfigPath}')

            if gamePaksDir:
                sprintPad()
                sprint(f'Locating pakchunk sources...')
                notFoundPakchunks = []
                pakchunkSourceMap = {}
                gamePakchunkFilenameRelPathMap = {}
                for relPath in gamePakchunks:
                    filename = os.path.basename(relPath)
                    gamePakchunkFilenameRelPathMap[filename] = relPath

                for relPath in modsToBeActive:
                    filename = os.path.basename(relPath)
                    if filename in pakingDirPakchunks:
                        pakchunkSourceMap[relPath] = source = normPath(os.path.join(pakingDir, filename))
                    elif filename in gamePakchunkFilenameRelPathMap:
                        pakchunkSourceMap[relPath] = source = normPath(os.path.join(gamePaksDir, gamePakchunkFilenameRelPathMap[filename]))
                    else:
                        printError(f'Pakchunk (to install) not found: {filename}')
                        hasError = True
                        notFoundPakchunks.append(filename)
                        source = None

                    if source is not None and debug:
                        sprint(f'"{relPath}" <- "{source}"')

                pakchunksToActivate = [p for p in modsToBeActive if p not in gamePakchunks]
                sprintPad()
                sprint(f'Pakchunks to activate: {len(pakchunksToActivate)}')
                for i, pakchunkRelPath in enumerate(pakchunksToActivate):
                    sprint(f'{i + 1} - {pakchunkRelPath}')

                pakchunksToDeactivate = [p for p in gamePakchunks if p not in modsToBeActive]
                sprintPad()
                sprint(f'Pakchunks to deactivate: {len(pakchunksToDeactivate)}')
                for i, pakchunkRelPath in enumerate(pakchunksToDeactivate):
                    sprint(f'{i + 1} - {pakchunkRelPath}')

                if not hasError and installingMods:
                    dryRun = False

                    noChanges = True

                    sprintPad()
                    sprint(f'Moving mods between "{pakingDir}" and "{gamePaksDir}"...')
                    for pakchunkRelPath in modsToBeActive:
                        source = pakchunkSourceMap[pakchunkRelPath]
                        dest = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                        if not os.path.exists(dest) or not os.path.samefile(source, dest):
                            sprint(f'Moving "{source}" to "[Paks]/{pakchunkRelPath}"')
                            if not dryRun:
                                if readyToWrite(dest):
                                    shutil.move(source, dest)
                                    noChanges = False
                                else:
                                    printWarning(f'Not allowed to overwrite "{pakchunkRelPath}"')

                    for pakchunkRelPath in pakchunksToDeactivate:
                        filename = os.path.basename(pakchunkRelPath)
                        source = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                        dest = normPath(os.path.join(pakingDir, filename))
                        if filename in pakingDirPakchunks:
                            sprint(f'Removing "[Paks]/{pakchunkRelPath}" which is also stored at "{dest}"')
                            if not dryRun:
                                if readyToWrite(source):
                                    pathlib.Path.unlink(source)
                                    noChanges = False
                        else:
                            sprint(f'Moving "{pakchunkRelPath}" to "{dest}"')
                            if not dryRun:
                                shutil.move(source, dest)
                                noChanges = False

                    if dryRun:
                        sprint('Done.')
                    else:
                        sprint(f'Installation succeeded{" - no changes" if noChanges else ""}.')
                    sprintPad()
    except Exception as e:
        printError(e)
        if debug:
            raise e

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
            'pakingDirPakchunks': pakingDirPakchunks,
            'gamePaksDir': gamePaksDir,
            'gamePakchunks': gamePakchunks,
            'modsToBeActive': modsToBeActive,
            'cookedContentDir': cookedContentDir,
            'cookedAssets': list(cookedContentAssetPathsMap.keys()),
            'cookedFiles': cookedContentPaths,
        }

        outputInfoFilename = getResultsFilePath(settingsFilePath)
        sprintPad()
        sprint(f'Writing command results to "{outputInfoFilename}"')
        # TODO: should we overwrite result file without confirming?
        if readyToWrite(outputInfoFilename, overwrite=True):
            with open(outputInfoFilename, 'w') as file:
                yamlDump(jsonifyDataRecursive(outputInfo), file)
        sprintPad()

    if openingGameLauncher:
        if not gameDir:
            printError('Missing or empty `gameDir`')
        else:
            sprintPad()
            sprint('Opening game launcher and starting game if not already running (exit the launcher to return)...')
            if nonInteractive:
                printError('Cannot open game launcher in non-interactive mode')
            else:
                warningOfLauncherClearScreen = not getSprintIsRecording()
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
                    shouldProceed = confirm('open the launcher and clear the screen buffer history', pad=True)
                else:
                    shouldProceed = True

                if shouldProceed:
                    gameIsRunning = getGameIsRunning()
                    try:
                        exitCode = openGameLauncher(getPathInfo(gameDir)['best'], startGame=not getGameIsRunning())
                        # clear any last bits of the launcher output left over
                        os.system('cls')
                        replaySprintRecording()
                    except Exception as e:
                        printError(e)
                    finally:
                        clearSprintRecording()
            sprintPad()

    return exitCode
