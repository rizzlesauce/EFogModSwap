import copy
import glob
import json
import os
import pathlib
import shutil
import tempfile
import time
import traceback
import uuid
from itertools import chain, combinations

import semver
import yaml
from pynput import keyboard

from modswap.helpers import tempFileHelpers
from modswap.helpers.attachmentAnimationBlueprintHelpers import getSkeletonPath
from modswap.helpers.attachmentBlueprintHelpers import (getAnimBlueprintPath,
                                                        getSkeletalMeshPath)
from modswap.helpers.attachmentHelpers import (basicAttachmentTemplate,
                                               getAttachmentDisplayName,
                                               getAttachmentFilename)
from modswap.helpers.consoleHelpers import (clearSprintRecording, confirm,
                                            confirmOverwrite, esprint,
                                            getConsoleWindow,
                                            getSprintIsRecording,
                                            oneLinePrinter, promptToContinue,
                                            replaySprintRecording, sprint,
                                            sprintClear, sprintP, sprintPad,
                                            sprintput, sprintSeparator,
                                            startSprintRecording)
from modswap.helpers.customizationItemDbHelpers import (
    AccessoryBlueprintName, AssetNameFieldName, AttachmentBlueprintName,
    CustomizationItemDbAssetName, ECustomizationCategoryName,
    ECustomizationCategoryNamePrefix, ModelDisplayNamePropNameFieldName,
    addAllToNameMap, findSocketAttachmentsStruct, generateRandomHexString,
    getAssetPath, getAssetPathProperty, getAssociatedCharacterId,
    getAttachmentBlueprintPath, getAttachmentBlueprintProperty,
    getAttachmentSkeletalMeshPath, getAttachmentSocketName,
    getItemMeshProperty, getModelDisplayNameProperty, getModelIdProperty,
    getModelName, getSocketAttachments, getUiDataValues, md5Hash, setModelName,
    sha256Hash, upgradeCustomizationItemDb)
from modswap.helpers.fileHelpers import listFilesRecursively
from modswap.helpers.gameHelpers import (DefaultGameVersion,
                                         DefaultPrevGameVersion,
                                         KnownSupportedGameVersions,
                                         getGameIsRunning,
                                         getGameLobbyIsRunning, getGamePaksDir,
                                         getGameServerIsRunning,
                                         getGameUnrealEngineVersion, killGame,
                                         killGameLobby, killGameServer,
                                         openGameLauncher)
from modswap.helpers.guiHelpers import getForegroundWindow
from modswap.helpers.jsonHelpers import jsonDump, jsonifyDataRecursive
from modswap.helpers.pakHelpers import (DefaultPlatform,
                                        PakchunkFilenameSuffix,
                                        getPakContentDir,
                                        pakchunkRefnamePartsDictToRefname,
                                        pakchunkRefnamePartsToRefname,
                                        pakchunkRefnameToFilename,
                                        pakchunkRefnameToParts,
                                        pakchunkToSigFilePath, unrealPak,
                                        unrealUnpak)
from modswap.helpers.pathHelpers import getPathInfo, normPath
from modswap.helpers.settingsHelpers import (DefaultAttachmentsDir,
                                             DefaultPakingDir,
                                             findSettingsFiles,
                                             getContentDirRelativePath,
                                             getGameName, getGameProgramName,
                                             getResultsFilePath,
                                             getSettingsTemplate)
from modswap.helpers.uassetHelpers import (AssetPathGamePrefix,
                                           ClassNameSkeletalMesh, ClassSuffix,
                                           ExportsFieldName, ImportsFieldName,
                                           NameFieldName, NameMapFieldName,
                                           PackageGuidFieldName,
                                           ValueFieldName, findEnumByType,
                                           findNextItemByFields,
                                           findNextItemByType, getEnumValue,
                                           getPropertyValue,
                                           getShortenedAssetPath, jsonToUasset,
                                           setPropertyValue, uassetToJson)
from modswap.helpers.umodelHelpers import (UmodelProgramStem,
                                           UmodelSaveFolderName,
                                           runUmodelCommand)
from modswap.helpers.unrealEngineHelpers import (
    UassetFilenameSuffix, UassetJsonSuffix, UbulkFilenameSuffix,
    UexpFilenameSuffix, UfontFilenameSuffix, UmapFilenameSuffix,
    getAssetSplitFilePaths, getAssetStemPathInfo,
    getUnrealProjectCookedContentDir)
from modswap.helpers.windowsHelpers import (getIsRunningAsAdmin, openFolder,
                                            setConsoleTitle)
from modswap.helpers.yamlHelpers import yamlDump
from modswap.metadata.programMetaData import ConsoleTitle

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

    with open(filePath, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)

    # TODO: ensure relative paths in settings are converted to relative paths
    # to relativeDir

    for otherPath in data.get('import', []):
        # import paths are relative to the file importing them
        otherData = readSettingsRecursive(otherPath, relativeDir=pathInfo['dir'], silent=silent)
        mergeSettings(resultData, otherData)

    mergeSettings(resultData, data)

    return resultData


class ModSwapCommandRunner():
    DryRunPrefix = '[DryRun] '

    def __init__(self):
        self.warnings = []
        self.errors = []
        self.exitCode = 0
        self.nonInteractive = False
        self.debug = False
        self.dryRun = False
        self.overwriteOverride = None
        self.dryRunPrefix = ''
        self.dryRunDirsCreated = set()
        self.attachmentsDir = None
        self.exportAttachmentsSeparator = '_'
        self.uassetGuiPath = None
        self.umodelPath = None
        self.unrealEngineVersion = None
        self.gameVersion = None
        self.prevGameVersion = None
        if False:
            self.importAttachmentsSeparator = 'And'
        else:
            self.importAttachmentsSeparator = '_'
        self.listener = None
        self.shouldView = False
        self.searchingSlots = None
        self.wroteResults = False

    def getUmodelGameTag(self):
        if self.unrealEngineVersion:
            return f'ue{self.unrealEngineVersion}'

        raise ValueError(f'Could not determine {UmodelProgramStem} game tag')

    def startKeyboardListener(self, shouldStartPaused=False):
        if self.listener:
            self.stopKeyboardListener()

        if self.nonInteractive:
            return lambda **kwargs: True

        shouldContinue = True

        pauseCharMap = {
            'p': '',
            'd': 'inDataJson',
            'b': 'inBlueprintJson',
        }

        shouldPauseIn = {}
        needsPauseNotify = {}

        def togglePause(pauseChar):
            pauseIn = pauseCharMap.get(pauseChar, None)
            if pauseIn is not None:
                shouldPauseIn[pauseIn] = not shouldPauseIn.get(pauseIn, False)

                if shouldPauseIn[pauseIn]:
                    def doIt():
                        sprintSeparator()
                        sprint(f'Paused{f" {pauseIn}" if pauseIn else ""}. Press {pauseChar} to unpause')
                    needsPauseNotify[pauseIn] = doIt
                else:
                    sprintSeparator()
                    needsPauseNotify.pop(pauseIn, None)

        if shouldStartPaused:
            togglePause('p')

        def onKeyPress(key):
            nonlocal shouldContinue

            # TODO: is there a better library or method to not pick up keyboard input while another program is in focus?
            if getForegroundWindow() != getConsoleWindow():
                return

            if key == keyboard.Key.esc or (hasattr(key, 'char') and key.char in ('q', 'x', 'k')):
                shouldContinue = not shouldContinue
                # stop the listener
                # TODO: remove
                if False:
                    return False
            elif hasattr(key, 'char') and key.char in pauseCharMap:
                togglePause(key.char)
            elif (hasattr(key, 'char') and key.char in ('v')):
                self.shouldView = not self.shouldView
                sprintPad()
                sprint(f'Viewing meshes: {self.shouldView}')
                sprintPad()
            elif (hasattr(key, 'char') and key.char in ('s')):
                self.searchingSlots = not self.searchingSlots
                sprintPad()
                sprint(f'Searching slots: {self.searchingSlots}')
                sprintPad()

        def checkInput(**kwargs):
            nonlocal shouldContinue

            pauseInKeys = [''] + [key for key in kwargs.keys() if key in pauseCharMap.values()]

            while any(shouldPauseIn[pauseIn] for pauseIn in pauseInKeys if pauseIn in shouldPauseIn) and shouldContinue:
                for key, func in list(needsPauseNotify.items()):
                    try:
                        func()
                    except Exception as e:
                        sprintPad()
                        esprint(e)
                        sprintPad()
                    finally:
                        needsPauseNotify.pop(key, None)

                time.sleep(.5)

            return shouldContinue

        self.listener = keyboard.Listener(on_press=onKeyPress)
        self.listener.start()

        return checkInput

    def stopKeyboardListener(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

    def printWarning(self, message, pad=True):
        self.warnings.append(str(message))
        if pad:
            sprintPad()
        sprint(f'WARN: {message}')
        if pad:
            sprintPad()

    def printError(self, error, pad=True, setExitCode=True):
        if setExitCode:
            self.exitCode = 1

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
            self.errors.append(str(line))

        if pad:
            sprintPad()

        for line in (traceLines if self.debug else lines):
            esprint(f'ERROR: {line}')

        if pad:
            sprintPad()

    def readyToWrite(self, path, delete=True, overwrite=None, dryRunHere=None):
        path = getPathInfo(path)['best']

        if dryRunHere is None:
            dryRunHere = self.dryRun

        dryRunHerePrefix = self.DryRunPrefix if dryRunHere else ''

        if not os.path.exists(path):
            return True

        shouldWarn = True

        if overwrite is not None:
            result = overwrite
        elif self.overwriteOverride is not None:
            result = self.overwriteOverride
        elif self.nonInteractive:
            self.printWarning('Cannot confirm file overwrite in non-interactive mode')
            result = False
        else:
            result = confirmOverwrite(path, prefix=dryRunHerePrefix, emptyMeansNo=True)
            shouldWarn = False

        if result:
            if shouldWarn or dryRunHere:
                self.printWarning(f'{dryRunHerePrefix}Overwriting "{path}"')
        elif shouldWarn:
            self.printWarning(f'Skipping write of "{path}" (file exists)')

        if result and delete and not dryRunHere:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                pathlib.Path.unlink(path)

        return result

    def ensureDir(self, dir, title='Folder', warnIfNotExist=True):
        dir = getPathInfo(dir)['best']
        if not os.path.exists(dir) and (not self.dryRun or dir not in self.dryRunDirsCreated):
            if warnIfNotExist or self.dryRun:
                self.printWarning(f'{title or "Folder"} "{dir}" does not exist. {self.dryRunPrefix}Creating it now...')
            shouldWrite = not self.dryRun or (not self.nonInteractive and confirm(f'Create folder "{dir}" despite dry run', pad=True, emptyMeansNo=True))
            written = False
            if shouldWrite:
                os.makedirs(dir, exist_ok=True)
                written = True
            if (written or self.dryRun) and warnIfNotExist or self.dryRun:
                sprint(f'{self.dryRunPrefix if not written else ""}Done creating.')
                sprintPad()
            if self.dryRun:
                self.dryRunDirsCreated.add(dir)
        return dir

    def ensureAttachmentsDir(self):
        return self.ensureDir(self.attachmentsDir, '`attachmentsDir`')

    def readUassetDataFromJson(self, customizationItemDbJsonPath, silent=False):
        result = None
        if not silent:
            sprintPad()
            sprint(f'Reading {CustomizationItemDbAssetName} JSON from "{customizationItemDbJsonPath}"...')
        with open(customizationItemDbJsonPath, 'r', encoding='utf-8') as file:
            result = json.load(file)
        if not silent:
            sprint('Done reading.')
            sprintPad()
        return result

    def readDataFromUasset(
        self,
        customizationItemDbPath,
        customizationItemDbJsonPath,
        dryRunHere=False,
        silent=False,
    ):
        dryRunHerePrefix = self.DryRunPrefix if dryRunHere else ''
        if not silent:
            sprintPad()
            sprint(f'{dryRunHerePrefix}Converting "{customizationItemDbPath}" to JSON, writing "{customizationItemDbJsonPath}"...')

        if not os.path.exists(self.uassetGuiPath):
            raise ValueError(f'`uassetGuiPath` "{self.uassetGuiPath}" does not exist')

        shouldWrite = not dryRunHere or (not self.nonInteractive and confirm(f'write {CustomizationItemDbAssetName} JSON "{customizationItemDbJsonPath}" despite dry run, to read data', pad=True, emptyMeansNo=True))
        written = False
        if shouldWrite:
            if self.readyToWrite(customizationItemDbJsonPath, overwrite=True, dryRunHere=False):
                uassetToJson(
                    customizationItemDbPath,
                    customizationItemDbJsonPath,
                    self.uassetGuiPath,
                    self.unrealEngineVersion,
                )
                # TODO: remove isfile check if not needed
                written = True or os.path.isfile(customizationItemDbJsonPath)
        if not silent:
            if written or dryRunHere:
                sprint(f'{dryRunHerePrefix if not written else ""}Done converting.')
            sprintPad()

        if written:
            return self.readUassetDataFromJson(customizationItemDbJsonPath, silent=silent)

        if shouldWrite:
            raise ValueError(f'Unable to convert "{customizationItemDbPath}" to JSON')

    def processCustomizationItemDb(self,
        asset,
        inspecting=False,
        upgrading=False,
        mixingAttachments=False,
        extractingAttachments=False,
        attachmentsCreated=None,
        attachmentsToMix=None,
        categoryCombinationsToSkip=None,
        categoryCombinationSubsetsToSkip=None,
        categoryCombinationsRequired=None,
        categoryCombinationSubsetsRequired=None,
        settingsPathInfo=None,
        assetStemPathSourceFilesMap=None,
        umodelCwdPathInfo=None,
        gamePaksDirPathInfo=None,
        writingAlteredDb=False,
        searchingGameAssets=False,
        checkInput=None,
    ):
        if attachmentsCreated is None:
            attachmentsCreated = []
        if attachmentsToMix is None:
            attachmentsToMix = {}
        if categoryCombinationsToSkip is None:
            categoryCombinationsToSkip = {}
        if categoryCombinationSubsetsToSkip is None:
            categoryCombinationSubsetsToSkip = {}
        if categoryCombinationsRequired is None:
            categoryCombinationsRequired = {}
        if categoryCombinationSubsetsRequired is None:
            categoryCombinationSubsetsRequired = {}
        if checkInput is None:
            checkInput = lambda **kwargs: True

        customizationItemDb = asset['data']
        customizationItemDbPathInfo = asset['pathInfo']
        customizationItemDbContentDirRelativePath = asset.get('contentDirRelativePath', None)

        sprintPad()
        sprint(f'Processing CustomizationItemDB "{customizationItemDbPathInfo["best"]}"...')
        sprintPad()

        if upgrading:
            sprintPad()
            sprint(f'{self.dryRunPrefix}Upgrading CustomizationItemDB at "{customizationItemDbPathInfo["best"]}" from game version {self.prevGameVersion} to {self.gameVersion}...')
            upgradeCustomizationItemDb(customizationItemDb, self.prevGameVersion, self.gameVersion, dryRun=False, debug=self.debug)
            sprint(f'{self.dryRunPrefix}Done upgrading.')
            sprintPad()
            asset[f'upgraded-{self.prevGameVersion}-{self.gameVersion}'] = True

        if inspecting or searchingGameAssets or mixingAttachments or extractingAttachments:
            exports = customizationItemDb[ExportsFieldName]
            dataTableExport = findNextItemByType(exports, 'UAssetAPI.ExportTypes.DataTableExport, UAssetAPI')
            models = dataTableExport['Table']['Data']
            modelsCopy = models.copy()
            if mixingAttachments:
                models.clear()
                combinationsSkipped = {}
                combinationsAdded = {}
                asset['combinationsAdded'] = combinationsAdded
                asset['combinationsSkipped'] = combinationsSkipped

            sprintPad()
            sprint(f'Reading {len(modelsCopy)} models...')
            for modelIndex, model in enumerate(modelsCopy):
                if not checkInput():
                    break
                try:
                    modelName = getModelName(model)
                    sprintPad()
                    sprint(f'{modelIndex + 1} - reading {modelName}...')

                    modelValues = getPropertyValue(model)

                    modelIdProp = getModelIdProperty(modelValues, self.gameVersion)
                    modelId = getPropertyValue(modelIdProp)
                    if modelId != modelName:
                        self.printWarning(f'ID ({modelId}) does not match model name ({modelName})')

                    modelNameParts = modelName.split('_')
                    modelBaseName = modelNameParts.pop(0)
                    sprint(f'Base Name: {modelBaseName}')

                    meshAssetShortStemPath = getShortenedAssetPath(
                        getAssetPath(
                            getPropertyValue(
                                getItemMeshProperty(modelValues),
                            ),
                        ),
                    )
                    sprint(f'Mesh: {meshAssetShortStemPath or "(none)"}')

                    associatedCharacterId = getAssociatedCharacterId(modelValues)
                    sprint(f"Character ID: {'(none)' if associatedCharacterId is None else associatedCharacterId}")

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
                    elif categoryName == 'KillerBody':
                        shortCategoryName = 'Body'
                    elif categoryName == 'KillerHead':
                        shortCategoryName = 'Head'
                    elif categoryName == 'KillerWeapon':
                        shortCategoryName = 'Weapon'
                    elif categoryName == 'Charm':
                        shortCategoryName = 'Charm'
                    else:
                        raise ValueError(f'Unsupported customization category: {categoryFullName}')

                    sprint(f'Category: {categoryName}')

                    socketAttachments = getSocketAttachments(modelValues)
                    sprint(f'Attachments: {len(socketAttachments)}')

                    if len(socketAttachments):
                        # TODO: ignore this - it's not a reliable way of determining attachment names
                        otherNames = [n for n in modelNameParts if n.lower() not in {'torso', 'legs', 'head', 'body', 'weapon', 'outfits', 'charm'}]
                        otherNamesString = '_'.join(otherNames)
                        attachmentNames = otherNamesString.split(self.importAttachmentsSeparator) if otherNamesString else []

                        if self.debug:
                            sprint(f"Potential attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        attachmentDisplayNamesString = ''
                        openParenIndex = modelDisplayName.find('(')
                        if openParenIndex > -1:
                            closeParenIndex = modelDisplayName.find(')', openParenIndex + 1)
                            if closeParenIndex > -1:
                                attachmentDisplayNamesString = modelDisplayName[(openParenIndex + 1):closeParenIndex]

                        if self.debug:
                            sprint(f'Potential attachments display names string: {attachmentDisplayNamesString}')

                        attachmentDisplayNames = attachmentDisplayNamesString.split(', ') if attachmentDisplayNamesString else []
                        if self.debug:
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

                        if self.debug:
                            sprint(f"Synthesized attachments names: {', '.join(attachmentNames) if attachmentNames else '(unknown)'}")

                        if extractingAttachments or searchingGameAssets:
                            for attachmentIndex, attachmentData in enumerate(socketAttachments):
                                if not checkInput():
                                    break

                                animBlueprintShortStemPath = None
                                meshShortStemPath = None

                                attachmentValues = getPropertyValue(attachmentData, [])
                                socketName = getAttachmentSocketName(attachmentValues)
                                skeletalMeshShortStemPath = getShortenedAssetPath(
                                    getAttachmentSkeletalMeshPath(attachmentValues),
                                )
                                blueprintPath = getAttachmentBlueprintPath(attachmentValues, self.gameVersion)
                                blueprintShortStemPath = getShortenedAssetPath(blueprintPath)
                                sprint(f'- Attachment {attachmentIndex + 1}:{f" {socketName}" if socketName else ""}{f" {blueprintShortStemPath}" if blueprintPath else ""}{f" {skeletalMeshShortStemPath}" if skeletalMeshShortStemPath else ""}')
                                if blueprintPath is None and skeletalMeshShortStemPath is None:
                                    sprintP(attachmentValues)

                                if searchingGameAssets and blueprintPath and self.umodelPath and umodelCwdPathInfo and gamePaksDirPathInfo:
                                    # TODO: remove
                                    if False:
                                        sprint('Reading attachment blueprint...')
                                    # try to load the attachment blueprint to discover the mesh
                                    try:
                                        saveFilePath = self.saveAsset(
                                            gamePaksDirPathInfo['absolute'],
                                            umodelCwdPathInfo['absolute'],
                                            blueprintShortStemPath,
                                            silent=True,
                                        )
                                    except Exception as e:
                                        self.printError(e)
                                        saveFilePath = None

                                    if saveFilePath and checkInput():
                                        try:
                                            # TODO: remove
                                            if False:
                                                sprint(f'Searching "{saveFilePath}"...')
                                            saveFileDir = os.path.dirname(saveFilePath)
                                            saveFileStem = os.path.basename(saveFilePath).removesuffix(UassetFilenameSuffix)
                                            with tempFileHelpers.openTemporaryFile(
                                                saveFileDir,
                                                prefix=f'{saveFileStem}_',
                                                suffix='.json',
                                                deleteFirst=True,
                                            ) as saveFileJsonFile:
                                                saveFileJsonPath = getPathInfo(saveFileJsonFile.name)['best']
                                                try:
                                                    blueprintData = self.readDataFromUasset(
                                                        saveFilePath,
                                                        saveFileJsonPath,
                                                        silent=True,
                                                    )
                                                except Exception as e:
                                                    blueprintData = None
                                                    self.printError(e)

                                                if blueprintData:
                                                    if False:
                                                        for name in blueprintData[NameMapFieldName]:
                                                            if not checkInput():
                                                                break
                                                            sprint(name)
                                                    imports = blueprintData.get(ImportsFieldName, [])
                                                    animBlueprintShortStemPath = getShortenedAssetPath(
                                                        getAnimBlueprintPath(imports)
                                                    )
                                                    sprint(f'  - Animation blueprint: {animBlueprintShortStemPath or "(none)"}')
                                                    meshShortStemPath = getShortenedAssetPath(
                                                        getSkeletalMeshPath(imports)
                                                    )
                                                    sprint(f'  - Attachment mesh: {meshShortStemPath or "(none)"}')
                                                    if meshShortStemPath and self.shouldView:
                                                        fullMeshPath = f'{"" if meshShortStemPath.startswith("/") else AssetPathGamePrefix}{meshShortStemPath}{UassetFilenameSuffix}'
                                                        viewReturnCode = None
                                                        viewError = False
                                                        for viewStreamName, viewLine, viewStop in runUmodelCommand(
                                                            self.umodelPath,
                                                            [
                                                                '-view',
                                                                f'-game={self.getUmodelGameTag()}',
                                                                f'-path={gamePaksDirPathInfo["absolute"]}',
                                                                fullMeshPath,
                                                                # TODO: remove
                                                                #ClassNameSkeletalMesh,
                                                            ],
                                                            cwd=umodelCwdPathInfo['absolute'],
                                                            debug=self.debug,
                                                        ):
                                                            if not checkInput():
                                                                viewStop()
                                                            if viewStreamName == 'return_code':
                                                                viewReturnCode = viewLine
                                                            elif viewStreamName == 'stderr' and 'ERROR' in viewLine:
                                                                self.printError(viewLine)
                                                                viewError = viewLine
                                                            elif self.debug:
                                                                sprint(viewLine)
                                                        if viewReturnCode or viewError:
                                                            self.printError(f'Failed to view "{fullMeshPath}"')

                                                checkInput(inBlueprintJson=True)
                                        finally:
                                            for path in getAssetSplitFilePaths(saveFilePath):
                                                pathlib.Path.unlink(path, missing_ok=True)

                                nameIsh = socketName
                                if not nameIsh and blueprintPath:
                                    nameIsh = os.path.basename(blueprintPath)
                                if not nameIsh and skeletalMeshShortStemPath:
                                    nameIsh = os.path.basename(skeletalMeshShortStemPath)
                                if not nameIsh and modelDisplayName:
                                    nameIsh = modelDisplayName.replace(' ', '_')
                                if not nameIsh and modelName:
                                    nameIsh = modelName

                                displayNameIsh = modelDisplayName
                                if not displayNameIsh and modelName:
                                    displayNameIsh = modelName
                                if not displayNameIsh and nameIsh:
                                    displayNameIsh = nameIsh

                                if extractingAttachments:
                                    if attachmentIndex < len(attachmentNames):
                                        attachmentId = attachmentNames[attachmentIndex]
                                    else:
                                        attachmentId = '_'.join([part for part in [nameIsh, f'{attachmentIndex + 1}'] if part])

                                    if attachmentIndex < len(attachmentDisplayNames):
                                        attachmentDisplayName = attachmentDisplayNames[attachmentIndex]
                                    else:
                                        attachmentDisplayName = ' '.join(
                                            part for part in [
                                                displayNameIsh,
                                                'Attachment' if len(socketAttachments) > 1 else '',
                                                f'{attachmentIndex + 1}/{len(socketAttachments)}' if len(socketAttachments) > 1 else '',
                                            ] if part
                                        )

                                    filename = f'SocketAttachment_{modelBaseName}_{shortCategoryName}_{attachmentId}.yaml'
                                    filePath = getPathInfo(os.path.join(self.ensureAttachmentsDir(), filename))['best']

                                    if os.path.exists(filePath):
                                        self.printWarning(f'Skipping attachment {attachmentIndex + 1} (file already exists): "{filePath}"', pad=False)
                                    else:
                                        sprint(f'{self.dryRunPrefix}Extracting attachment {attachmentIndex + 1}: {attachmentId} ({attachmentDisplayName}) to "{filePath}"')

                                        attachmentInfo = {
                                            'attachmentId': attachmentId,
                                            'modelCategory': categoryName,
                                            'displayName': attachmentDisplayName,
                                            'associatedModelId': modelName,
                                            'associatedCharacterId': associatedCharacterId,
                                            'associatedCharacterMesh': meshAssetShortStemPath,
                                            'animationBlueprint': animBlueprintShortStemPath,
                                            'attachmentMesh': meshShortStemPath,
                                            'attachmentData': attachmentData,
                                        }

                                        if not self.dryRun:
                                            with open(filePath, 'w', encoding='utf-8') as file:
                                                yamlDump(attachmentInfo, file)

                                        attachmentsCreated.append(filePath)
                    elif mixingAttachments:
                        shouldAddThisModel = True
                        emptySet = frozenset()

                        if shouldAddThisModel:
                            if emptySet in categoryCombinationsToSkip.get(categoryName, {}):
                                baseModels = categoryCombinationsToSkip[categoryName][emptySet]
                                if not baseModels or modelBaseName in baseModels:
                                    shouldAddThisModel = False

                        if shouldAddThisModel:
                            if emptySet in categoryCombinationSubsetsToSkip.get(categoryName, {}):
                                baseModels = categoryCombinationsToSkip[categoryName][emptySet]
                                if not baseModels or modelBaseName in baseModels:
                                    shouldAddThisModel = False

                        if shouldAddThisModel:
                            sprintPad()
                            sprint(f'Adding base model {categoryName}::{modelBaseName}')
                            sprintPad()
                            models.append(model)
                        else:
                            sprintPad()
                            sprint(f'Skipping base model {categoryName}::{modelBaseName}')
                            sprintPad()

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
                                if not checkInput():
                                    break

                                # TODO: use names instead of values in combinations()
                                for combo in combinations(attachmentsForCategory.values(), r):
                                    if not checkInput():
                                        break

                                    attachmentIds = [a['attachmentId'] for a in combo]

                                    attachmentIdsSet = frozenset(attachmentIds)

                                    shouldSkipCombo = None

                                    if shouldSkipCombo is None:
                                        baseModels = categoryCombinationsToSkip.get(categoryName, {}).get(attachmentIdsSet, None)
                                        if baseModels is not None:
                                            if len(baseModels) == 0 or modelBaseName in baseModels:
                                                shouldSkipCombo = True

                                    if shouldSkipCombo is None:
                                        for combosToSkip, baseModels in categoryCombinationSubsetsToSkip.get(categoryName, {}).items():
                                            if (len(baseModels) == 0 or modelBaseName in baseModels) and combosToSkip <= attachmentIdsSet:
                                                shouldSkipCombo = True
                                                break

                                    if shouldSkipCombo is None:
                                        for combosRequired, baseModels in categoryCombinationsRequired.get(categoryName, {}).items():
                                            if len(baseModels) and modelBaseName not in baseModels:
                                                continue

                                            if combosRequired != attachmentIdsSet:
                                                shouldSkipCombo = True
                                                break

                                    if shouldSkipCombo is None:
                                        for combosRequired, baseModels in categoryCombinationSubsetsRequired.get(categoryName, {}).items():
                                            if len(baseModels) and modelBaseName not in baseModels:
                                                continue

                                            if not combosRequired <= attachmentIdsSet:
                                                shouldSkipCombo = True
                                                break

                                    if shouldSkipCombo is None:
                                        # allow all by default
                                        shouldSkipCombo = False

                                    if shouldSkipCombo:
                                        if self.debug:
                                            if modelBaseName not in combinationsSkipped:
                                                combinationsSkipped[modelBaseName] = {}
                                            if categoryName not in combinationsSkipped[modelBaseName]:
                                                combinationsSkipped[modelBaseName][categoryName] = set()
                                            combinationsSkipped[modelBaseName][categoryName].add(attachmentIdsSet)
                                        continue

                                    # TODO: maybe only do this if self.debug ?
                                    if True:
                                        if modelBaseName not in combinationsAdded:
                                            combinationsAdded[modelBaseName] = {}
                                        if categoryName not in combinationsAdded[modelBaseName]:
                                            combinationsAdded[modelBaseName][categoryName] = set()
                                        combinationsAdded[modelBaseName][categoryName].add(attachmentIdsSet)
                                    comboCount += 1

                                    attachmentNamesString = self.exportAttachmentsSeparator.join(attachmentIds)
                                    attachmentDisplayNames = [getAttachmentDisplayName(a) for a in combo]
                                    attachmentDisplayNamesString = ', '.join([name for name in attachmentDisplayNames if name])
                                    newModelDisplayName = f'{modelDisplayNameBase}{f" ({attachmentDisplayNamesString})" if attachmentDisplayNamesString else ""}'
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
                                    newModelIdProp = getModelIdProperty(newModelValues, self.gameVersion)
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
                                        # Correct the blueprint property name for different game versions
                                        attachmentValues = getPropertyValue(attachment['attachmentData'])
                                        blueprintAttachmentProperty = getAttachmentBlueprintProperty(attachmentValues)
                                        if semver.VersionInfo.parse(self.gameVersion) >= semver.VersionInfo.parse('6.5.2'):
                                            if blueprintAttachmentProperty[NameFieldName] != AccessoryBlueprintName:
                                                blueprintAttachmentProperty[NameFieldName] = AccessoryBlueprintName
                                                if self.debug:
                                                    sprint(f'- Changing attachment blueprint property name field to `{blueprintAttachmentProperty[NameFieldName]}`')
                                        else:
                                            if blueprintAttachmentProperty[NameFieldName] != AttachmentBlueprintName:
                                                blueprintAttachmentProperty[NameFieldName] = AttachmentBlueprintName
                                                if self.debug:
                                                    sprint(f'- Changing attachment blueprint property name field to `{blueprintAttachmentProperty[NameFieldName]}`')

                                        newSocketAttachments.append(attachment['attachmentData'])

                                    # TODO: alter model icons and descriptions if specified

                                    models.append(newModel)
                            sprint(f'Created {comboCount} combos')
                            sprintPad()
                except Exception as e:
                    self.printError(e)
            sprintPad()
            sprint('Models processed.')
            sprintPad()

        if mixingAttachments:
            nameMapArray = customizationItemDb[NameMapFieldName]
            nameMapArrayCopy = nameMapArray.copy()
            nameMapArray.clear()
            nameMapSet = set()
            addAllToNameMap(customizationItemDb.get(ImportsFieldName, []), nameMapSet)
            addAllToNameMap(customizationItemDb.get(ExportsFieldName, []), nameMapSet)

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
                    # only on UE 4.27 (>= EFog 6.5.2)?
                    'FloatProperty',
                    'ByteProperty',
                }:
                    nameMapSet.add(name)

            # TODO: remove? doesn't seem to be required
            if False:
                customizationItemDbName = next((name for name in nameMapArrayCopy if name.startswith(f'{AssetPathGamePrefix}Data/Dlc/') and name.endswith(f'/{CustomizationItemDbAssetName}')), None)
                if customizationItemDbName:
                    nameMapSet.add(customizationItemDbName)

            for name in nameMapSet:
                nameMapArray.append(name)
            nameMapArray.sort(key=lambda v: v.upper())

            nameMapSetOld = set(nameMapArrayCopy)

            nameMapNamesRemoved = nameMapSetOld - nameMapSet
            nameMapNamesAdded = nameMapSet - nameMapSetOld

            asset['nameMapAlterations'] = {
                'namesAdded': nameMapNamesAdded,
                'namesRemoved': nameMapNamesRemoved,
            },

            if self.debug:
                sprintPad()
                sprint(f'{NameMapFieldName} names removed:')
                sprint(yamlDump(jsonifyDataRecursive(nameMapNamesRemoved)))
                sprintPad()

            if self.debug:
                sprintPad()
                sprint(f'{NameMapFieldName} names added:')
                sprint(yamlDump(jsonifyDataRecursive(nameMapNamesAdded)))
                sprintPad()

        if upgrading or mixingAttachments:
            if writingAlteredDb:
                jsonOutPath = getPathInfo(os.path.join(
                    settingsPathInfo['dir'],
                    # TODO: make path unique if writing multiple CustomizationItemDB assets
                    f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.json",
                ))['best']
                sprintPad()
                sprint(f'{self.dryRunPrefix}Writing altered {CustomizationItemDbAssetName} to "{jsonOutPath}"...')
                shouldWrite = not self.dryRun
                written = False
                if shouldWrite:
                    if self.readyToWrite(jsonOutPath, overwrite=True, dryRunHere=False):
                        with open(jsonOutPath, 'w', encoding='utf-8') as file:
                            jsonDump(customizationItemDb, file, pretty=True)
                            written = True
                if written or self.dryRun:
                    sprint(f'{self.dryRunPrefix if not written else ""}Done writing.')
                sprintPad()

                if customizationItemDbPathInfo['suffixLower'] == UassetFilenameSuffix:
                    customizationItemDbDestContentDir = None
                    if customizationItemDbContentDirRelativePath is not None:
                        customizationItemDbDestContentDir = getPathInfo(os.path.join(settingsPathInfo['dir'], f'{customizationItemDbPathInfo["stem"]}-{settingsPathInfo["stem"]}'))['best']
                        customizationItemDbDestDir = getPathInfo(os.path.join(customizationItemDbDestContentDir, os.path.dirname(customizationItemDbContentDirRelativePath)))['best']
                        customizationItemDbPathInfo = getPathInfo(os.path.join(customizationItemDbDestDir, customizationItemDbPathInfo['basename']))

                    sprintPad()
                    sprint(f'{self.dryRunPrefix}Writing altered {CustomizationItemDbAssetName} to "{customizationItemDbPathInfo["best"]}"...')
                    if os.path.exists(self.uassetGuiPath):
                        shouldWrite = not self.dryRun
                        written = False
                        if shouldWrite:
                            if self.readyToWrite(customizationItemDbPathInfo['best'], dryRunHere=False):
                                self.ensureDir(customizationItemDbPathInfo['dir'], f'{CustomizationItemDbAssetName} dest folder')
                                jsonToUasset(jsonOutPath, customizationItemDbPathInfo['best'], self.uassetGuiPath)
                                written = True
                        if written or self.dryRun:
                            sprint(f'{self.dryRunPrefix if not written else ""}Done writing.')
                            if (
                                customizationItemDbContentDirRelativePath is not None
                                and customizationItemDbDestContentDir is not None
                                and assetStemPathSourceFilesMap is not None
                            ):
                                assetStemPath = getAssetStemPathInfo(customizationItemDbContentDirRelativePath)['stemPath']
                                assetStemPathSourceFilesMap[assetStemPath] = {
                                    'contentDir': customizationItemDbDestContentDir,
                                    'fileSuffixes': [UassetFilenameSuffix, UexpFilenameSuffix],
                                }
                                if self.debug:
                                    sprintPad()
                                    sprint(customizationItemDbContentDirRelativePath)
                                    sprint(assetStemPath)
                                    sprint(assetStemPathSourceFilesMap[assetStemPath])

                        sprintPad()
                    else:
                        self.printError(f'`uassetGuiPath` "{self.uassetGuiPath}" does not exist')

                if self.debug:
                    yamlOutPath = getPathInfo(os.path.join(
                        settingsPathInfo['dir'],
                        # TODO: make path unique if writing multiple CustomizationItemDB assets
                        f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-altered.yaml",
                    ))['best']
                    sprintPad()
                    sprint(f'{self.dryRunPrefix}Writing altered {CustomizationItemDbAssetName} to "{yamlOutPath}"...')
                    shouldWrite = not self.dryRun
                    written = False
                    if shouldWrite:
                        if self.readyToWrite(yamlOutPath, overwrite=True, dryRunHere=False):
                            with open(yamlOutPath, 'w', encoding='utf-8') as file:
                                yamlDump(customizationItemDb, file)
                                written = True
                    if written or self.dryRun:
                        sprint(f'{self.dryRunPrefix if not written else ""}Done writing.')
                    sprintPad()

        sprintPad()
        sprint('Done processing.')
        sprintPad()

    def saveAsset(self, paksDir, destDir, assetPath, silent=False, setExitCode=True):
        assetPath = assetPath.removesuffix(UassetFilenameSuffix)
        assetStem = os.path.basename(assetPath)

        packagePath = f'{assetPath}{UassetFilenameSuffix}'
        if not packagePath.startswith('/'):
            packagePath = f'{AssetPathGamePrefix}{packagePath}'

        if not silent:
            sprint(f'Extracting {assetStem}...')

        paksDirPathInfo = getPathInfo(paksDir)

        umodelCwdPathInfo = getPathInfo(destDir)
        saveReturnCode = None
        saveError = None
        for saveStreamName, saveLine, saveStop in runUmodelCommand(
            self.umodelPath,
            [
                '-save',
                f'-game={self.getUmodelGameTag()}',
                f'-path={paksDirPathInfo["absolute"]}',
                packagePath,
            ],
            cwd=umodelCwdPathInfo['absolute'],
            debug=self.debug,
        ):
            if saveStreamName == 'return_code':
                saveReturnCode = saveLine
            elif saveStreamName == 'stderr' and 'ERROR' in saveLine:
                self.printError(saveLine, setExitCode=setExitCode)
                saveError = saveLine
                saveStop()
        if saveReturnCode or saveError:
            message = f'Failed to extract "{packagePath}"'
            raise ValueError(message)

        saveFilePackageRelPath = packagePath.removeprefix('/')
        saveFilePath = normPath(os.path.join(umodelCwdPathInfo['best'], UmodelSaveFolderName, saveFilePackageRelPath))
        if not os.path.isfile(saveFilePath):
            message = f'Asset not saved to the expected location: "{saveFilePath}"'
            if self.debug and not self.nonInteractive:
                self.printError(message)
                promptToContinue()
            raise ValueError(message)

        if not silent:
            sprint('Done extracting.')

        return saveFilePath

    def runCommand(self, **kwargs):
        """ Main entry point of the app """

        settingsFilePath = kwargs.get('settingsFilePath', '')
        activeModConfigName = kwargs.get('activeModConfigName', '')
        inspecting = kwargs.get('inspecting', False)
        creatingAttachments = kwargs.get('creatingAttachments', False)
        extractingAttachments = kwargs.get('extractingAttachments', False)
        renamingAttachmentFiles = kwargs.get('renamingAttachmentFiles', False)
        mixingAttachments = kwargs.get('mixingAttachments', False)
        upgradingMods = kwargs.get('upgradingMods', False)
        paking = kwargs.get('paking', False)
        installingMods = kwargs.get('installingMods', False)
        openingGameLauncher = kwargs.get('openingGameLauncher', False)
        killingGame = kwargs.get('killingGame', False)
        self.nonInteractive = kwargs.get('nonInteractive', False)
        self.debug = kwargs.get('debug', False)
        self.uassetGuiPath = kwargs.get('uassetGuiPath', '')
        unrealPakPath = kwargs.get('unrealPakPath', '')
        sigFilePath = kwargs.get('sigFilePath', None)
        self.umodelPath = kwargs.get('umodelPath', '')
        self.overwriteOverride = kwargs.get('overwriteOverride', None)
        launcherStartsGame = kwargs.get('launcherStartsGame', None)
        fromMenu = kwargs.get('fromMenu', False)
        self.dryRun = kwargs.get('dryRun', False)
        gameDir = kwargs.get('gameDir', None)
        self.gameVersion = (kwargs.get('gameVersion', None) or '').strip()
        self.prevGameVersion = (kwargs.get('prevGameVersion', None) or '').strip()
        pakingDir = kwargs.get('pakingDir', None)
        self.attachmentsDir = kwargs.get('attachmentsDir', None)
        extraContentDir = kwargs.get('extraContentDir', None)
        unrealProjectDir = kwargs.get('unrealProjectDir', None)
        searchingGameAssets = kwargs.get('searchingGameAssets', False)
        self.searchingSlots = kwargs.get('searchingSlots', None)
        self.unrealEngineVersion = kwargs.get('unrealEngineVersion', None)
        srcPakPath = (kwargs.get('srcPakPath', None) or '').strip()
        customizationItemDbPath = (kwargs.get('customizationItemDbPath', None) or '').strip()

        # TODO: attachmemt filters: characterID(s), item role(s), attachment type(s)
        # TODO: be able to specify regex and case insensitivity
        prevSearchResume = None
        searchPakchunkNameMatchers = None
        searchAssetNameMatchers = None
        searchNameMapNameMatchers = None
        searchJsonStringMatchers = None
        searchBinaryAsciiMatchers = None

        longestAsciiMatcher = None

        searchResume = {
            'pakchunkRelStemPath': None,
            'assetPath': None,
        }

        searchAssetMatchesFile = None
        searchNameMapMatchesFile = None
        searchJsonStringMatchesFile = None
        searchBinaryAsciiMatchesFile = None

        openFiles = []

        def appendYamlFileResult(file, items):
            file.write(yamlDump(jsonifyDataRecursive(items)))
            file.flush()

        self.dryRunPrefix = self.DryRunPrefix if self.dryRun else ''

        self.wroteResults = False

        launcherClearsScreenBuffer = False
        if launcherStartsGame is None:
            launcherStartsGame = DefaultLauncherStartsGame

        if openingGameLauncher and not self.dryRun and launcherClearsScreenBuffer:
            startSprintRecording()

        # TODO: remove -- too verbose
        printingJson = False
        printingYaml = False

        writingUnalteredDb = self.debug

        settingsFilePathInfo = getPathInfo(settingsFilePath)

        settingsDirPathInfo = getPathInfo(settingsFilePathInfo['dir'])
        discoveredSettingsFiles = []

        if inspecting:
            sprintPad()
            sprint(f'Scanning "{settingsDirPathInfo["best"]}" for settings files...')
            for filename in findSettingsFiles(settingsDirPathInfo['absolute']):
                discoveredSettingsFiles.append(filename)
                sprint(f'{len(discoveredSettingsFiles)} - {filename}')
            sprint(f'Done scanning. Discovered {len(discoveredSettingsFiles)} settings files')
            sprintPad()

        settingsFilePath = settingsFilePathInfo['best']
        settings = {}

        cookedContentDir = ''
        cookedContentPaths = []
        sourceDirDestAssetsMap = {}
        extraContentPaths = []
        cookedContentAssetPathsMap = {}
        extraContentAssetPathsMap = {}
        gamePaksDir = ''
        gamePakchunks = []
        modConfigNameGroupsMap = {}
        modGroupNamePakchunksMap = {}
        reservedPakchunks = None
        targetActiveMods = []
        pakingDirPakchunkStems = []
        gameName = ''
        gameProgramName = ''
        srcPakStem = ''
        srcPakDir = ''
        srcPakDirAlreadyExisted = None
        srcPakDirWasWritten = False
        srcPakNumber = -1
        srcPakName = None
        srcPakPlatform = None
        srcPakPlatformSuffix = None
        assetStemPathSourceFilesMap = {}
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

        customizationItemDbAssets = []

        equivalentParts = {}
        supersetParts = {}
        mutuallyExclusive = {}
        attachmentConflicts = {}
        combosToSkip = {}
        combosRequired = {}

        categoryCombinationsToSkip = {}
        categoryCombinationSubsetsToSkip = {}
        categoryCombinationsRequired = {}
        categoryCombinationSubsetsRequired = {}
        attachmentsToMix = {}
        attachmentsCreated = []
        attachmentsRenamed = {}

        def ensurePakingDir():
            return self.ensureDir(pakingDir, '`pakingDir`')

        def checkAttachmentName(category, attachmentName, otherInfo=None):
            if attachmentName not in attachmentsToMix.get(category, {}):
                self.printWarning(f"reference to missing attachment: {category}::{attachmentName}{' (' if otherInfo else ''}{otherInfo or ''}{')' if otherInfo else ''}")

        try:
            if not os.path.exists(settingsFilePath):
                self.printWarning(f'Settings file "{settingsFilePath}" does not exist. {self.dryRunPrefix}Creating it now with default content...')
                yamlStringContent = getSettingsTemplate(
                    gameDir=gameDir,
                    gameVersion=self.gameVersion,
                    prevGameVersion=self.prevGameVersion,
                    pakingDir=pakingDir,
                    attachmentsDir=self.attachmentsDir,
                    extraContentDir=extraContentDir,
                    unrealProjectDir=unrealProjectDir,
                    uassetGuiPath=self.uassetGuiPath,
                    unrealPakPath=unrealPakPath,
                    unrealEngineVersion=self.unrealEngineVersion,
                    sigFilePath=sigFilePath,
                    umodelPath=self.umodelPath,
                )
                if printingYaml:
                    sprint(yamlStringContent)
                    sprintPad()
                shouldWrite = not self.dryRun or (not self.nonInteractive and confirm(f'write settings file "{settingsFilePath}" despite dry run', pad=True, emptyMeansNo=True))
                written = False
                if shouldWrite:
                    with open(settingsFilePath, 'w', encoding='utf-8') as file:
                        file.write(yamlStringContent)
                        written = True
                if written or self.dryRun:
                    sprint(f'{self.dryRunPrefix if not written else ""}Done creating.')
                sprintPad()

            settingsPathInfo = getPathInfo(settingsFilePath)
            settingsDir = settingsPathInfo['dir']
            settings = readSettingsRecursive(settingsFilePath)

            srcPakPath = getPathInfo((settings.get('srcPakPath', None) or '').strip() or srcPakPath)['best']
            if not srcPakPath and inspecting:
                self.printWarning(f'Missing or empty `srcPakPath`')

            unrealPakPath = settings.get('unrealPakPath', unrealPakPath)
            unrealPakPath = unrealPakPath or ''
            unrealPakPath = getPathInfo(unrealPakPath)['best']
            if not unrealPakPath:
                if (
                    inspecting
                    or paking
                    or (
                        srcPakPath and (
                            extractingAttachments
                            or upgradingMods
                            or mixingAttachments
                        )
                    )
                ):
                    self.printWarning('Missing or empty `unrealPakPath`')
            elif not os.path.isfile(unrealPakPath):
                self.printError(f'`unrealPakPath` is not a file ("{unrealPakPath}")')
                unrealPakPath = ''

            if not sigFilePath:
                sigFilePath = settings.get('sigFilePath', '')
            sigFilePath = sigFilePath or ''
            sigFilePath = getPathInfo(sigFilePath)['best']
            if not sigFilePath:
                if (
                    inspecting
                    or paking
                ):
                    self.printWarning('Missing or empty `sigFilePath`')
            elif not os.path.isfile(sigFilePath):
                self.printError(f'`sigFilePath` is not a file ("{sigFilePath}")')
                sigFilePath = ''

            customizationItemDbPath = (settings.get('customizationItemDbPath', None) or '').strip() or customizationItemDbPath
            if not customizationItemDbPath and inspecting:
                self.printWarning(f'Missing or empty `customizationItemDbPath`')

            self.uassetGuiPath = settings.get('uassetGuiPath', self.uassetGuiPath)
            self.uassetGuiPath = self.uassetGuiPath or ''
            self.uassetGuiPath = getPathInfo(self.uassetGuiPath)['best']
            if not self.uassetGuiPath:
                if (
                    inspecting
                    or (
                        customizationItemDbPath
                        and (
                            extractingAttachments
                            or upgradingMods
                            or mixingAttachments
                        )
                    )
                ):
                    self.printWarning('Missing or empty `uassetGuiPath`')
            elif not os.path.isfile(self.uassetGuiPath):
                self.printError(f'`uassetGuiPath` is not a file ("{self.uassetGuiPath}")')
                self.uassetGuiPath = ''

            self.umodelPath = settings.get('umodelPath', self.umodelPath)
            self.umodelPath = self.umodelPath or ''
            self.umodelPath = getPathInfo(self.umodelPath)['best']
            if not self.umodelPath:
                if (
                    inspecting
                    or searchingGameAssets
                ):
                    self.printWarning('Missing or empty `umodelPath`')
            elif not os.path.isfile(self.umodelPath):
                self.printError(f'`umodelPath` is not a file ("{self.umodelPath}")')
                self.umodelPath = ''

            pakingDir = settings.get('pakingDir', pakingDir)
            pakingDir = pakingDir or ''
            pakingDir = getPathInfo(pakingDir)['best']
            if not pakingDir:
                pakingDir = getPathInfo(f'{DefaultPakingDir}-{self.gameVersion}')['best']
                if (
                    inspecting
                    or extractingAttachments
                    or upgradingMods
                    or mixingAttachments
                    or paking
                    or installingMods
                ):
                    self.printWarning(f'Missing or empty `pakingDir`. Defaulting to "{pakingDir}"')

            self.attachmentsDir = settings.get('attachmentsDir', self.attachmentsDir)
            self.attachmentsDir = self.attachmentsDir or ''
            self.attachmentsDir = getPathInfo(self.attachmentsDir)['best']
            if not self.attachmentsDir:
                self.attachmentsDir = getPathInfo(f'{DefaultAttachmentsDir}-{self.gameVersion}')['best']
                if (
                    inspecting
                    or extractingAttachments
                    or creatingAttachments
                    or renamingAttachmentFiles
                    or mixingAttachments
                ):
                    self.printWarning(f'Missing or empty `attachmentsDir`. Defaulting to "{self.attachmentsDir}"')

            gameDir = settings.get('gameDir', gameDir)
            gameDir = gameDir or ''
            gameDir = getPathInfo(gameDir)['best']
            if not gameDir:
                if inspecting:
                    self.printWarning('Missing or empty `gameDir`')
            elif not os.path.isdir(gameDir):
                self.printWarning(f'`gameDir` is not a directory or does not exist ("{gameDir}")')
                gameDir = ''

            if not gameName:
                gameName = getGameName(settings)
            if not gameName:
                if inspecting:
                    self.printWarning('Missing or empty `gameName`')
            else:
                sprintPad()
                sprint(f'Game: {gameName}')
                sprintPad()

            message = 'Missing, empty, or unresolved `gameProgramName`'
            if not gameProgramName:
                # TODO: notify if using default program name?
                gameProgramName = getGameProgramName(settings) or ''
            gameProgramName = gameProgramName.strip()
            if not gameProgramName:
                if killingGame:
                    self.printError(message)
                elif inspecting:
                    self.printWarning(message)

            self.gameVersion = (settings.get('gameVersion', None) or '').strip() or self.gameVersion
            if not self.gameVersion:
                self.gameVersion = DefaultGameVersion
                if inspecting:
                    self.printWarning(f'Missing or empty `gameVersion`. Defaulting to {self.gameVersion}')

            if self.debug:
                sprint(f'Game version: {self.gameVersion}')

            if self.gameVersion not in KnownSupportedGameVersions:
                self.printWarning(f'Game version may not be supported')

            self.prevGameVersion = (settings.get('prevGameVersion', None) or '').strip() or self.prevGameVersion
            if not self.prevGameVersion:
                self.prevGameVersion = DefaultPrevGameVersion
                if inspecting:
                    self.printWarning(f'Missing or empty `prevGameVersion`. Defaulting to {self.prevGameVersion}')

            if self.debug:
                sprint(f'Previous game version: {self.prevGameVersion}')

            self.unrealEngineVersion = (
                settings.get('unrealEngineVersion', None)
                or getGameUnrealEngineVersion(self.gameVersion)
                or self.unrealEngineVersion
                or None
            )
            if not self.unrealEngineVersion:
                if inspecting:
                    self.unrealEngineVersion = getGameUnrealEngineVersion(DefaultGameVersion)
                    self.printWarning(f'Missing or empty `unrealEngineVersion`. Defaulting to {self.unrealEngineVersion}')

            if self.debug:
                sprint(f'Unreal engine version: {self.unrealEngineVersion}')

            if not extraContentDir:
                extraContentDir = settings.get('extraContentDir', '')
            extraContentDir = extraContentDir or ''
            extraContentDir = getPathInfo(extraContentDir)['best']
            if not extraContentDir:
                if (
                    inspecting
                    or extractingAttachments
                    or upgradingMods
                    or mixingAttachments
                    or paking
                ):
                    self.printWarning(f'Missing or empty `extraContentDir`')

            unrealProjectDir = settings.get('unrealProjectDir', unrealProjectDir)
            unrealProjectDir = unrealProjectDir or ''
            unrealProjectDir = getPathInfo(unrealProjectDir)['best']
            if not unrealProjectDir:
                if (
                    inspecting
                    or extractingAttachments
                    or upgradingMods
                    or mixingAttachments
                    or paking
                ):
                    self.printWarning(f'Missing or empty `unrealProjectDir`')
            elif not os.path.isdir(unrealProjectDir):
                self.printError(f'`unrealProjectDir` is not a directory ("{unrealProjectDir}")')
                unrealProjectDir = ''

            if destPakNumber is None:
                destPakNumber = int(settings.get('destPakNumber', -1))
            if destPakNumber < 0 and (
                inspecting
                or paking
            ):
                self.printWarning(f'Missing, empty, or invalid `destPakNumber`')

            if not destPakName:
                destPakName = settings.get('destPakName', '')
            destPakName = destPakName.strip()
            if not destPakName and (
                inspecting
                or paking
            ):
                self.printWarning(f'Missing or empty `destPakName`')

            if destPakAssets is None:
                destPakAssets = settings.get('destPakAssets', None)

            if destPakAssets is None:
                if inspecting:
                    self.printWarning('Missing `destPakAssets`')
            elif not destPakAssets:
                if inspecting or paking:
                    self.printWarning('Empty `destPakAssets`')
            else:
                destPakAssets = [getPathInfo(p)['normalized'] for p in destPakAssets]

            if not activeModConfigName:
                activeModConfigName = settings.get('activeModConfig', '')
            activeModConfigName = (activeModConfigName or '').strip()
            if not activeModConfigName:
                message = 'No active mod config (missing `activeModConfig`)'
                if installingMods:
                    self.printError(message)
                elif inspecting:
                    self.printWarning(message)

            if not modConfigNameGroupsMap:
                modConfigNameGroupsMap = settings.get('modConfigs', {})
            if not modConfigNameGroupsMap:
                message = 'Missing or empty `modConfigs`'
                if installingMods:
                    self.printError(message)
                elif inspecting:
                    self.printWarning(message)

            if not modGroupNamePakchunksMap:
                modGroupNamePakchunksMap = settings.get('modGroups', {})
            if not modGroupNamePakchunksMap:
                message = 'Missing or empty `modGroups`'
                if installingMods:
                    self.printError(message)
                elif inspecting:
                    self.printWarning(message)

            if reservedPakchunks is None:
                reservedPakchunks = settings.get('reservedPakchunks', [])
            if not reservedPakchunks:
                self.printWarning(f'Missing or empty `reservedPakchunks`')

            if not equivalentParts:
                equivalentParts = settings.get('equivalentParts', {})
            if not equivalentParts and inspecting:
                self.printWarning('Missing or empty `equivalentParts`')

            if not supersetParts:
                supersetParts = settings.get('supersetParts', {})
            if not supersetParts and inspecting:
                self.printWarning('Missing or empty `supersetParts`')

            if not mutuallyExclusive:
                mutuallyExclusive = settings.get('mutuallyExclusive', {})
            if not mutuallyExclusive and inspecting:
                self.printWarning('Missing or empty `mutuallyExclusive`')

            if not attachmentConflicts:
                attachmentConflicts = settings.get('attachmentConflicts', {})
            if not attachmentConflicts and inspecting:
                self.printWarning('Missing or empty `attachmentConflicts`')

            if not combosToSkip:
                combosToSkip = settings.get('combosToSkip', {})
            if not combosToSkip and inspecting:
                self.printWarning('Missing or empty `combosToSkip`')

            if not combosRequired:
                combosRequired = settings.get('combosRequired', {})
            if not combosRequired and inspecting:
                self.printWarning('Missing or empty `combosRequired`')

            if prevSearchResume is None:
                prevSearchResume = settings.get('searchResume', None)

            if searchPakchunkNameMatchers is None:
                searchPakchunkNameMatchers = settings.get('searchPakchunkNameMatchers', None)
            searchPakchunkNameMatchers = searchPakchunkNameMatchers or []

            if searchAssetNameMatchers is None:
                searchAssetNameMatchers = settings.get('searchAssetNameMatchers', None)
            searchAssetNameMatchers = searchAssetNameMatchers or []

            if searchNameMapNameMatchers is None:
                searchNameMapNameMatchers = settings.get('searchNameMapNameMatchers', None)
            searchNameMapNameMatchers = searchNameMapNameMatchers or []

            if searchJsonStringMatchers is None:
                searchJsonStringMatchers = settings.get('searchJsonStringMatchers', None)
            searchJsonStringMatchers = searchJsonStringMatchers or []

            if searchBinaryAsciiMatchers is None:
                searchBinaryAsciiMatchers = settings.get('searchBinaryAsciiMatchers', None)
            searchBinaryAsciiMatchers = searchBinaryAsciiMatchers or []
            searchBinaryAsciiMatchers = [m.lower() for m in searchBinaryAsciiMatchers]
            longestAsciiMatcher = next(reversed(sorted(searchBinaryAsciiMatchers, key=lambda x: len(x))), None)

            if self.searchingSlots is None:
                self.searchingSlots = settings.get('searchingSlots', None)
            if self.searchingSlots is None:
                self.searchingSlots = False

            if (installingMods and not self.exitCode) or searchingGameAssets or creatingAttachments or inspecting:
                sprintPad()
                sprint(f'Resolving game Paks folder...')

                if not gameDir:
                    message = f'Cannot resolve game Paks folder (missing or invalid `gameDir`)'
                    if installingMods:
                        self.printError(message)
                    else:
                        self.printWarning(message)

                if not gameName:
                    message = f'Cannot resolve game Paks folder (missing `gameName`)'
                    if installingMods:
                        self.printError(message)
                    else:
                        self.printWarning(message)

                if gameDir and gameName:
                    gamePaksDir = getGamePaksDir(gameDir, gameName)
                    sprint('Done resolving.')
                    sprintPad()
                    if not os.path.isdir(gamePaksDir):
                        self.printError(f'Game paks folder does not exist ("{gamePaksDir}")')
                        gamePaksDir = ''

            if killingGame and gameProgramName:
                sprintPad()
                sprint(f'{self.dryRunPrefix}Killing game...')
                isRunningAsAdmin = getIsRunningAsAdmin()
                if getGameIsRunning(gameProgramName):
                    shouldDoIt = True
                    # TODO: make this configurable, so it doesn't have to run as admin if not necessary
                    asAdmin = not isRunningAsAdmin
                    if asAdmin:
                        sprint('Must gain elevated access to kill game')
                        if self.nonInteractive:
                            self.printError('Cannot gain elevated access in non-interactive mode')
                        else:
                            shouldDoIt = confirm('continue to UAC', emptyMeansNo=False)

                    if shouldDoIt:
                        didIt = False
                        if not self.dryRun:
                            killExitCode = killGame(gameProgramName, asAdmin=asAdmin)
                            if killExitCode:
                                self.printError(f'killing game returned exit code: {killExitCode}')
                            else:
                                didIt = True
                        if didIt:
                            sprint(f'{self.dryRunPrefix}Game process terminated.')
                            # TODO: need to wait?
                    else:
                        sprint('Skipping killing game.')
                else:
                    sprint('Game is not running.')
                sprintPad()

                if semver.VersionInfo.parse(self.gameVersion) == semver.VersionInfo.parse('4.4.2'):
                    sprintPad()
                    sprint(f'{self.dryRunPrefix}Killing game lobby...')
                    if getGameLobbyIsRunning():
                        shouldDoIt = True
                        asAdmin = not isRunningAsAdmin
                        if asAdmin:
                            sprint('Must gain elevated access to kill lobby')
                            if self.nonInteractive:
                                self.printError('Cannot gain elevated access in non-interactive mode')
                            else:
                                shouldDoIt = confirm('continue to UAC', emptyMeansNo=False)

                        if shouldDoIt:
                            didIt = False
                            if not self.dryRun:
                                killExitCode = killGameLobby(asAdmin=asAdmin)
                                if killExitCode:
                                    self.printError(f'killing lobby returned exit code: {killExitCode}')
                                else:
                                    didIt = True
                            if didIt:
                                sprint(f'{self.dryRunPrefix}Lobby process terminated.')
                                # TODO: need to wait?
                        else:
                            sprint('Skipping killing lobby.')
                    else:
                        sprint('Lobby is not running.')
                    sprintPad()

                if semver.VersionInfo.parse(self.gameVersion) == semver.VersionInfo.parse('4.4.2'):
                    sprintPad()
                    sprint(f'{self.dryRunPrefix}Killing game server...')
                    if getGameServerIsRunning():
                        didIt = False
                        if not self.dryRun:
                            killExitCode = killGameServer()
                            if killExitCode:
                                self.printError(f'killing server returned exit code: {killExitCode}')
                            else:
                                didIt = True
                        if didIt:
                            sprint(f'{self.dryRunPrefix}Server process terminated.')
                        # TODO: need to wait?
                    else:
                        sprint('Server is not running.')
                    sprintPad()

            if creatingAttachments:
                if self.nonInteractive:
                    self.printWarning('Cannot create attachment definition in non-interactive mode')
                else:
                    done = False
                    canceled = False
                    hasError = False

                    def confirmCanceled():
                        nonlocal canceled
                        canceled = True
                        return canceled

                    def printError(*args):
                        nonlocal hasError

                        hasError = True
                        self.printError(*args, setExitCode=False)

                    sprintPad()
                    sprint('Attachment definition creator')
                    sprintPad()
                    self.ensureAttachmentsDir()
                    while not done:
                        attachment = copy.deepcopy(basicAttachmentTemplate)

                        gotOtherDetails = False
                        canceled = False
                        hasError = False

                        def getOtherDetails():
                            nonlocal gotOtherDetails

                            gotOtherDetails = True

                            attachment['modelCategory'] = ''
                            categoryOptions = {
                                'SurvivorTorso',
                                'SurvivorLegs',
                                'SurvivorHead',
                                'KillerBody',
                                'KillerHead',
                                'KillerWeapon',
                                'Charm',
                            }
                            while True:
                                hasError = False
                                attachment['modelCategory'] = sprintput(f"Model category ({', '.join(categoryOptions)}): ").strip()
                                if not attachment['modelCategory']:
                                    if confirmCanceled():
                                        break
                                    else:
                                        continue

                                if attachment['modelCategory'] not in categoryOptions:
                                    printError('Unsupported category')
                                    continue

                                break

                            if canceled:
                                return

                            attachment['attachmentId'] = ''
                            while True:
                                hasError = False
                                attachment['attachmentId'] = sprintput('Attachment ID: ').strip()
                                if not attachment['attachmentId']:
                                    if confirmCanceled():
                                        break
                                    else:
                                        continue

                                filename = getAttachmentFilename(attachment['attachmentId'])
                                filePath = normPath(os.path.join(self.ensureAttachmentsDir(), filename))
                                if os.path.exists(filePath):
                                    printError('Attachment ID already exists')
                                    continue

                                break

                            if canceled:
                                return

                            attachment['displayName'] = ''
                            while not attachment['displayName']:
                                attachment['displayName'] = sprintput('Display name: ').strip()
                                if not attachment['displayName']:
                                    #  allow it to be empty
                                    attachment['displayName'] = None
                                    break

                                break

                            if canceled:
                                return

                            sprint(f'{self.dryRunPrefix}Writing attachment definition to "{filePath}"...')
                            shouldWrite = not self.dryRun or (not self.nonInteractive and confirm(f'write attachment definition "{filePath}" despite dry run', pad=True, emptyMeansNo=True))
                            written = False
                            if shouldWrite:
                                if self.readyToWrite(filePath, dryRunHere=False):
                                    with open(filePath, 'w', encoding='utf-8') as file:
                                        yamlDump(attachment, file)
                                        written = True
                            if written or self.dryRun:
                                sprint(f'{self.dryRunPrefix if not written else ""}Done writing.')
                            sprintPad()

                            return True

                        attachmentValues = getPropertyValue(attachment['attachmentData'])
                        attachmentBlueprintProperty = getAttachmentBlueprintProperty(attachmentValues)
                        if semver.VersionInfo.parse(self.gameVersion) >= semver.VersionInfo.parse('6.5.2'):
                            attachmentBlueprintProperty[NameFieldName] = AccessoryBlueprintName
                        assetPath = getAssetPathProperty(getPropertyValue(attachmentBlueprintProperty))
                        assetPath[AssetNameFieldName] = ''
                        while True:
                            gotOtherDetails = False
                            hasError = False

                            def confirmBlueprint():
                                blueprintConfirmed = confirm('use this blueprint', pad=True, emptyMeansNo=True if hasError else False)
                                if not blueprintConfirmed:
                                    return

                                # TODO: remove
                                extraDebug = False
                                if extraDebug:
                                    confirmed = confirm('are you sure', pad=True)
                                    if not confirmed:
                                        return

                                return True

                            assetPath[AssetNameFieldName] = sprintput('Blueprint path: ').strip().removesuffix(UassetFilenameSuffix)
                            if not assetPath[AssetNameFieldName]:
                                if confirmCanceled():
                                    break
                                else:
                                    continue

                            try:
                                path = pathlib.PurePosixPath(assetPath[AssetNameFieldName])
                            except:
                                printError('Invalid game path')
                                continue

                            if assetPath[AssetNameFieldName].endswith('/') or assetPath[AssetNameFieldName].endswith('\\'):
                                printError('Should not be a directory')
                                continue

                            stem = path.stem
                            if not stem:
                                printError('Invalid game path')
                                continue

                            suffix = f'.{stem}{ClassSuffix}'
                            if path.suffix:
                                if path.suffix != suffix:
                                    printError('Invalid path suffix. Should be {suffix}')
                                    continue
                            else:
                                path = path.with_name(f'{stem}{suffix}')

                            normalizedPath = path.as_posix()
                            if not normalizedPath.startswith('/'):
                                normalizedPath = f'{AssetPathGamePrefix}{normalizedPath}'
                            sprint(f'Normalized path: {normalizedPath}')
                            assetPath[AssetNameFieldName] = normalizedPath

                            if gamePaksDir and self.umodelPath and extraContentDir:
                                # try to load the attachment blueprint
                                blueprintShortStemPath = getShortenedAssetPath(normalizedPath)
                                blueprintStem = os.path.basename(blueprintShortStemPath)
                                blueprintPackageStemPath = f'{"" if blueprintShortStemPath.startswith("/") else AssetPathGamePrefix}{blueprintShortStemPath}'
                                gamePaksDirPathInfo = getPathInfo(gamePaksDir)

                                sprintPad()
                                sprint(f'Extracting blueprint {blueprintStem}...')

                                with tempfile.TemporaryDirectory(
                                    dir=settingsDir,
                                    prefix=f'attachmentBlueprintData_{blueprintStem}_',
                                ) as tempDir:
                                    tempDirPathInfo = getPathInfo(tempDir)
                                    try:
                                        saveFilePath = self.saveAsset(
                                            gamePaksDirPathInfo['absolute'],
                                            tempDirPathInfo['absolute'],
                                            blueprintPackageStemPath,
                                            silent=True,
                                            setExitCode=False,
                                        )
                                    except Exception as e:
                                        printError(e)
                                        printError('Failed to extract blueprint.')
                                        saveFilePath = None

                                    if saveFilePath:
                                        sprint('Blueprint extracted.')
                                        sprintPad()

                                        try:
                                            saveFileDir = os.path.dirname(saveFilePath)
                                            saveFileStem = os.path.basename(saveFilePath).removesuffix(UassetFilenameSuffix)
                                            with tempFileHelpers.openTemporaryFile(
                                                saveFileDir,
                                                prefix=f'{saveFileStem}_',
                                                suffix='.json',
                                                deleteFirst=True,
                                            ) as saveFileJsonFile:
                                                blueprintJsonPath = getPathInfo(saveFileJsonFile.name)['best']
                                                sprintPad()
                                                sprint('Reading blueprint data...')
                                                try:
                                                    blueprintData = self.readDataFromUasset(
                                                        saveFilePath,
                                                        blueprintJsonPath,
                                                        silent=True,
                                                    )
                                                except Exception as e:
                                                    printError(e)
                                                    printError('Failed to read blueprint data.')
                                                    blueprintData = None

                                                if blueprintData:
                                                    # TODO: remove
                                                    if False:
                                                        for name in blueprintData[NameMapFieldName]:
                                                            sprint(name)
                                                    imports = blueprintData.get(ImportsFieldName, [])
                                                    animBlueprintShortStemPath = getShortenedAssetPath(
                                                        getAnimBlueprintPath(imports)
                                                    )
                                                    sprint(f'- Animation blueprint: {animBlueprintShortStemPath or "(none)"}')
                                                    animBlueprintPackageStemPath = f'{"" if animBlueprintShortStemPath.startswith("/") else AssetPathGamePrefix}{animBlueprintShortStemPath}' if animBlueprintShortStemPath else None
                                                    meshShortStemPath = getShortenedAssetPath(
                                                        getSkeletalMeshPath(imports)
                                                    )
                                                    meshPackageStemPath = f'{"" if meshShortStemPath.startswith("/") else AssetPathGamePrefix}{meshShortStemPath}' if meshShortStemPath else None
                                                    sprint(f'- Attachment mesh: {meshShortStemPath or "(none)"}')

                                                    def doViewMeshPart(animBlueprintData=None, animBlueprintJsonPath=None):
                                                        skeletonShortStemPath = None
                                                        skeletonPackageRelPath = None
                                                        if animBlueprintData:
                                                            skeletonShortStemPath = getShortenedAssetPath(
                                                                getSkeletonPath(animBlueprintData[ImportsFieldName])
                                                            )
                                                            skeletonPackageStemPath = f'{"" if skeletonShortStemPath.startswith("/") else AssetPathGamePrefix}{skeletonShortStemPath}' if skeletonShortStemPath else None
                                                            sprint(f'- Skeleton: {skeletonShortStemPath or "(none)"}')

                                                        if meshShortStemPath and (self.shouldView or True):
                                                            fullMeshPath = f'{meshPackageStemPath}{UassetFilenameSuffix}'
                                                            sprintPad()
                                                            sprint(f'Viewing mesh in {UmodelProgramStem} (close {UmodelProgramStem} window to continue)...')
                                                            sprintPad()
                                                            viewReturnCode = None
                                                            viewError = False
                                                            for viewStreamName, viewLine, viewStop in runUmodelCommand(
                                                                self.umodelPath,
                                                                [
                                                                    '-view',
                                                                    f'-game={self.getUmodelGameTag()}',
                                                                    f'-path={gamePaksDirPathInfo["absolute"]}',
                                                                    fullMeshPath,
                                                                    # TODO: remove
                                                                    #ClassNameSkeletalMesh,
                                                                ],
                                                                cwd=tempDirPathInfo['absolute'],
                                                                debug=self.debug,
                                                            ):
                                                                if viewStreamName == 'return_code':
                                                                    viewReturnCode = viewLine
                                                                elif viewStreamName == 'stderr' and 'ERROR' in viewLine:
                                                                    printError(viewLine)
                                                                    viewError = viewLine
                                                                    viewStop()
                                                                elif self.debug:
                                                                    sprint(viewLine)
                                                            if viewReturnCode or viewError:
                                                                printError(f'Failed to view "{fullMeshPath}"')

                                                        if confirmBlueprint():
                                                            if extraContentDir:
                                                                shouldCopy = confirm('copy to new blueprint', pad=True, emptyMeansNo=True)
                                                                if shouldCopy:
                                                                    self.ensureDir(extraContentDir, '`extraContentDir`')
                                                                    extraContentDirAbsolute = getPathInfo(extraContentDir)['absolute']
                                                                    newMeshPackageStemPath = sprintput('New skeletal mesh path: ').strip()
                                                                    if newMeshPackageStemPath:
                                                                        if not newMeshPackageStemPath.endswith('_REF'):
                                                                            newMeshPackageStemPath = f'{newMeshPackageStemPath}_REF'
                                                                        if not newMeshPackageStemPath.startswith('/'):
                                                                            newMeshPackageStemPath = f'{AssetPathGamePrefix}{newMeshPackageStemPath}'

                                                                        newAssetGameRelBaseStemPath = newMeshPackageStemPath.removeprefix(AssetPathGamePrefix).removesuffix('_REF')
                                                                        assert(not newAssetGameRelBaseStemPath.startswith('/'))
                                                                        newAssetBaseStem = os.path.basename(newAssetGameRelBaseStemPath)
                                                                        newAssetGameRelBaseDir = os.path.dirname(newAssetGameRelBaseStemPath)
                                                                        if newAssetGameRelBaseDir.endswith('/Models'):
                                                                            newAssetGameRelBaseDir = os.path.dirname(newAssetGameRelBaseDir)
                                                                        newBlueprintName = f'BP_{newAssetBaseStem}'
                                                                        newAssetsPackageRelBaseDir = f'{AssetPathGamePrefix}{newAssetGameRelBaseDir}'
                                                                        newGameRelBlueprintsDir = f'{newAssetGameRelBaseDir}/Blueprints'
                                                                        newBlueprintGameRelStemPath = f'{newGameRelBlueprintsDir}/{newBlueprintName}'
                                                                        newBlueprintPackageStemPath = f'{AssetPathGamePrefix}{newBlueprintGameRelStemPath}'
                                                                        newAnimBlueprintName = f'AB_{newAssetBaseStem}'
                                                                        newAnimBlueprintGameRelStemPath = f'{newGameRelBlueprintsDir}/{newAnimBlueprintName}'
                                                                        newAnimBlueprintPackageStemPath = f'{AssetPathGamePrefix}{newAnimBlueprintGameRelStemPath}'

                                                                        if True:
                                                                            newMeshName = os.path.basename(newMeshPackageStemPath)
                                                                            newSkeletonName = f'{newMeshName}_Skeleton'
                                                                            newSkeletonGameRelStemPath = f'{newAssetGameRelBaseDir}/Skeletons/{newSkeletonName}'
                                                                            newSkeletonPackageStemPath = f'{AssetPathGamePrefix}{newSkeletonGameRelStemPath}'
                                                                            jsonPaths = [blueprintJsonPath]
                                                                            if animBlueprintJsonPath:
                                                                                jsonPaths.append(animBlueprintJsonPath)

                                                                            meshName = os.path.basename(meshPackageStemPath) if meshPackageStemPath else None
                                                                            meshStem = meshName.removesuffix('_REF') if meshName else None
                                                                            blueprintName = os.path.basename(blueprintPackageStemPath)
                                                                            animBlueprintName = os.path.basename(animBlueprintPackageStemPath) if animBlueprintPackageStemPath else None
                                                                            assetsPackageRelBaseDir = os.path.dirname(os.path.dirname(blueprintPackageStemPath))

                                                                            newPhysicsAssetName = f'{newMeshName}_PhysicsAsset'
                                                                            newPhysicsAssetGameRelStemPath = f'{newAssetGameRelBaseDir}/Physics/{newPhysicsAssetName}'

                                                                            for path in jsonPaths:
                                                                                with open(path, 'r+', encoding='utf-8') as jsonFile:
                                                                                    sprintPad()
                                                                                    sprint(f'Updating temporary file {getPathInfo(path)["best"]}...')
                                                                                    jsonString = jsonFile.read()
                                                                                    def replace(original, replacement):
                                                                                        nonlocal jsonString
                                                                                        if self.debug:
                                                                                            sprint(f'Replacing "{original}" with "{replacement}"')
                                                                                        jsonString = jsonString.replace(original, replacement)

                                                                                    replace(blueprintPackageStemPath, newBlueprintPackageStemPath)
                                                                                    replace(blueprintName, newBlueprintName)
                                                                                    if meshPackageStemPath:
                                                                                        replace(meshPackageStemPath, newMeshPackageStemPath)
                                                                                    if meshName:
                                                                                        replace(meshName, newMeshName)
                                                                                    if animBlueprintPackageStemPath:
                                                                                        replace(animBlueprintPackageStemPath, newAnimBlueprintPackageStemPath)
                                                                                    if animBlueprintName:
                                                                                        replace(animBlueprintName, newAnimBlueprintName)
                                                                                    if skeletonPackageStemPath:
                                                                                        replace(skeletonPackageStemPath, newSkeletonPackageStemPath)
                                                                                    if meshStem:
                                                                                        replace(meshStem, newAssetBaseStem)

                                                                                    # TODO: remove? unnecessary
                                                                                    replace(assetsPackageRelBaseDir, newAssetsPackageRelBaseDir)
                                                                                    data = json.loads(jsonString)
                                                                                    newPackageGuid = '{' + str(uuid.uuid4()).upper() + '}'
                                                                                    if self.debug:
                                                                                        sprint(f'Changing {PackageGuidFieldName} from {data[PackageGuidFieldName]} to {newPackageGuid}')
                                                                                    data[PackageGuidFieldName] = newPackageGuid
                                                                                    jsonFile.seek(0)
                                                                                    jsonFile.truncate()
                                                                                    jsonDump(data, jsonFile, pretty=True)

                                                                            sprintPad()
                                                                            sprint('New asset paths (can add to `destPakAssets`):')
                                                                            sprintPad()
                                                                            sprint('# attachment blueprint assets (saved in `extraContentDir`)')
                                                                            sprint(f'- {newBlueprintGameRelStemPath}')
                                                                            sprint(f'- {newAnimBlueprintGameRelStemPath}')
                                                                            sprint('# attachment model assets (cooked in unreal engine)')
                                                                            sprint(f'- {newMeshPackageStemPath.removeprefix(AssetPathGamePrefix)}')
                                                                            sprint(f'- {newSkeletonGameRelStemPath}')
                                                                            sprint(f'- {newPhysicsAssetGameRelStemPath}')
                                                                            sprintPad()

                                                                        # TODO: apply dryRun logic
                                                                        if confirm('generate modified blueprint assets', pad=True, emptyMeansNo=False):
                                                                            blueprintsDir = normPath(os.path.join(extraContentDirAbsolute, newAssetGameRelBaseDir, 'Blueprints'))
                                                                            newBlueprintPath = normPath(os.path.join(blueprintsDir, f'{newBlueprintName}{UassetFilenameSuffix}'))
                                                                            if self.readyToWrite(newBlueprintPath):
                                                                                self.ensureDir(blueprintsDir, 'new Blueprints dest folder')
                                                                                jsonToUasset(blueprintJsonPath, newBlueprintPath, self.uassetGuiPath)
                                                                                assetPath[AssetNameFieldName] = f'{newBlueprintPackageStemPath}.{newBlueprintName}{ClassSuffix}'
                                                                            newAnimBlueprintPath = normPath(os.path.join(blueprintsDir, f'{newAnimBlueprintName}{UassetFilenameSuffix}'))
                                                                            if animBlueprintJsonPath and self.readyToWrite(newAnimBlueprintPath):
                                                                                self.ensureDir(blueprintsDir, 'new Blueprints dest folder')
                                                                                jsonToUasset(animBlueprintJsonPath, newAnimBlueprintPath, self.uassetGuiPath)
                                                                    else:
                                                                        # TODO: jsonToUasset using original blueprint locations
                                                                        pass
                                                            return True

                                                    if animBlueprintShortStemPath:
                                                        sprintPad()
                                                        sprint('Extracting animation blueprint...')
                                                        try:
                                                            animFilePath = self.saveAsset(
                                                                gamePaksDir,
                                                                tempDir,
                                                                animBlueprintShortStemPath,
                                                                silent=True,
                                                                setExitCode=False,
                                                            )
                                                        except Exception as e:
                                                            printError('Failed to extract animation blueprint.')
                                                            printError(e)
                                                            animFilePath = None

                                                        if animFilePath:
                                                            sprint('Animation blueprint extracted.')
                                                            sprintPad()

                                                            animFileDir = os.path.dirname(animFilePath)
                                                            animFileStem = os.path.basename(animFilePath).removesuffix(UassetFilenameSuffix)
                                                            with tempFileHelpers.openTemporaryFile(
                                                                animFileDir,
                                                                prefix=f'{animFileStem}_',
                                                                suffix='.json',
                                                                deleteFirst=True,
                                                            ) as animFileJsonFile:
                                                                animBlueprintJsonPath = getPathInfo(animFileJsonFile.name)['best']
                                                                sprintPad()
                                                                sprint('Reading animation blueprint data...')
                                                                try:
                                                                    animBlueprintData = self.readDataFromUasset(
                                                                        animFilePath,
                                                                        animBlueprintJsonPath,
                                                                        silent=True,
                                                                    )
                                                                except Exception as e:
                                                                    animBlueprintData = None
                                                                    printError(e)
                                                                    printError('Failed to read animation blueprint data.')

                                                                if doViewMeshPart(animBlueprintData, animBlueprintJsonPath):
                                                                    break
                                                        elif confirmBlueprint():
                                                            break
                                                    elif doViewMeshPart():
                                                        break
                                                elif confirmBlueprint():
                                                    break
                                        except Exception as e:
                                            printError(e)
                                        finally:
                                            for path in getAssetSplitFilePaths(saveFilePath):
                                                pathlib.Path.unlink(path, missing_ok=True)
                                    elif confirmBlueprint():
                                        break
                            elif confirmBlueprint():
                                break

                        if canceled:
                            break

                        if not gotOtherDetails:
                            getOtherDetails()

                        if canceled:
                            break

                        if not confirm('add another', emptyMeansNo=True):
                            done = True

                    if canceled:
                        sprintPad()
                        sprint(f'Add canceled.')
                        sprintPad()

            if (inspecting or extractingAttachments or upgradingMods or mixingAttachments or paking) and srcPakPath:
                sprintPad()
                sprint(f'Resolving source pak content folder...')
                if not gameName:
                    self.printError(f'Cannot resolve source pak content folder (missing `gameName`)')
                else:
                    if not os.path.exists(srcPakPath):
                        if not pathlib.Path(srcPakPath).suffix:
                            srcPakPath = f'{srcPakPath}{PakchunkFilenameSuffix}'
                            self.printWarning(f'Trying `srcPakPath` with "{PakchunkFilenameSuffix}" extension ("{srcPakPath})')

                    if not os.path.exists(srcPakPath):
                        self.printError(f'`srcPakPath` "{srcPakPath}" does not exist')
                    elif os.path.isdir(srcPakPath):
                        srcPakDir = srcPakPath
                    elif pathlib.Path(srcPakPath).suffix.lower() == PakchunkFilenameSuffix:
                        srcPakPathInfo = getPathInfo(srcPakPath)
                        srcPakDir = getPathInfo(os.path.join(ensurePakingDir(), srcPakPathInfo['stem']))['best']
                        srcPakDirAlreadyExisted = os.path.exists(srcPakDir)
                        sprintPad()
                        sprint(f'{self.dryRunPrefix}Unpaking "{srcPakPath}" to "{srcPakDir}"...')
                        if os.path.exists(unrealPakPath):
                            ensurePakingDir()
                            shouldWrite = not self.dryRun or (not self.nonInteractive and confirm(f'write to source pak folder "{srcPakDir}" despite dry run', pad=True, emptyMeansNo=True))
                            written = False
                            if shouldWrite:
                                if self.readyToWrite(srcPakDir, dryRunHere=False):
                                    checkInput = self.startKeyboardListener()
                                    try:
                                        unrealUnpak(srcPakPath, srcPakDir, gameName, unrealPakPath, debug=self.debug, checkInput=checkInput)
                                        written = True
                                    finally:
                                        self.stopKeyboardListener()
                            if written or self.dryRun:
                                sprint(f'{self.dryRunPrefix if not written else ""}Done unpaking.')
                            sprintPad()
                            srcPakDirWasWritten = written
                        else:
                            self.printError(f'`unrealPakPath` "{unrealPakPath}" does not exist')

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
                                self.printWarning('Source pakchunk filename has no name')
                            if not srcPakPlatform:
                                self.printWarning('Source pakchunk filename has no platform')
                            elif srcPakPlatform != destPlatform:
                                self.printWarning(f'Source pakchunk platform "{srcPakPlatform}" is different than "{destPlatform}"')
                        srcPakContentDir = getPakContentDir(srcPakDir, gameName)
                        sprintPad()
                        sprint(f'Reading pak content at "{srcPakContentDir}"...')
                        if os.path.isdir(srcPakContentDir):
                            for pathIndex, path in enumerate(listFilesRecursively(srcPakContentDir)):
                                srcPakContentPaths.append(path)
                                assetPathInfo = getAssetStemPathInfo(path)
                                stemPath = None
                                if assetPathInfo:
                                    stemPath = assetPathInfo['stemPath']
                                    pathSuffix = assetPathInfo['suffix']
                                else:
                                    self.printWarning(f'Unrecognized asset type: "{path}"')
                                    pathSuffix = pathlib.Path(path).suffix
                                    stemPath = path[:-len(pathSuffix)]

                                if stemPath:
                                    if stemPath not in srcPakContentAssetPathsMap:
                                        srcPakContentAssetPathsMap[stemPath] = []
                                        if self.debug:
                                            sprint(f'Asset {len(srcPakContentAssetPathsMap)}: "{stemPath}"')
                                    srcPakContentAssetPathsMap[stemPath].append(pathSuffix)
                                    if stemPath not in assetStemPathSourceFilesMap:
                                        assetStemPathSourceFilesMap[stemPath] = {
                                            'contentDir': srcPakContentDir,
                                            'fileSuffixes': srcPakContentAssetPathsMap[stemPath],
                                        }

                                if self.debug:
                                    sprint(f'{pathIndex + 1} - {path}')
                            if self.debug:
                                sprintPad()
                            sprint(f'Done reading. Discovered {len(srcPakContentAssetPathsMap)} pak assets ({len(srcPakContentPaths)} files)')
                            sprintPad()
                        else:
                            self.printError(f'Pak content folder "{srcPakContentDir}" does not exist')
                            srcPakContentDir = ''
                    sprint(f'Done resolving.')

            if (inspecting or extractingAttachments or upgradingMods or mixingAttachments or paking) and extraContentDir:
                if srcPakPath and not inspecting:
                    self.printWarning(f'Not looking for extra cooked content because `srcPakDir` has precedence')
                else:
                    sprintPad()
                    sprint(f'Reading extra cooked content at "{extraContentDir}"')
                    if os.path.isdir(extraContentDir):
                        for pathIndex, path in enumerate(listFilesRecursively(extraContentDir)):
                            extraContentPaths.append(path)
                            if path.lower().endswith(UassetJsonSuffix):
                                path = f'{path[:-len(UassetJsonSuffix)]}{UassetFilenameSuffix}'
                            assetPathInfo = getAssetStemPathInfo(path)
                            if assetPathInfo:
                                if assetPathInfo['stemPath'] not in extraContentAssetPathsMap:
                                    extraContentAssetPathsMap[assetPathInfo['stemPath']] = []
                                    if self.debug:
                                        sprint(f'Asset {len(extraContentAssetPathsMap)}: {assetPathInfo["stemPath"]}')
                                extraContentAssetPathsMap[assetPathInfo['stemPath']].append(assetPathInfo['suffix'])
                                if assetPathInfo['stemPath'] not in assetStemPathSourceFilesMap:
                                    assetStemPathSourceFilesMap[assetPathInfo['stemPath']] = {
                                        'contentDir': extraContentDir,
                                        'fileSuffixes': extraContentAssetPathsMap[assetPathInfo['stemPath']],
                                    }

                            if self.debug:
                                sprint(f'{pathIndex + 1} - {path}')
                        sprint(f'Done reading. Discovered {len(extraContentAssetPathsMap)} extra assets ({len(extraContentPaths)} files)')
                        sprintPad()
                    else:
                        self.printError(f'Extra content folder "{extraContentDir}" does not exist')
                        extraContentDir = ''

            if (inspecting or extractingAttachments or upgradingMods or mixingAttachments or paking) and unrealProjectDir:
                if srcPakPath and not inspecting:
                    self.printWarning(f'Not looking for unreal project cooked content because `srcPakDir` has precedence')
                else:
                    sprintPad()
                    sprint(f'Resolving unreal project cooked content folder...')
                    if not gameName:
                        self.printError(f'Cannot resolve unreal project cooked content folder (missing `gameName`)')
                    else:
                        cookedContentDir = getUnrealProjectCookedContentDir(unrealProjectDir, destPlatform, gameName)
                        sprintPad()
                        sprint(f'Reading cooked content at "{cookedContentDir}"')
                        if os.path.isdir(cookedContentDir):
                            for pathIndex, path in enumerate(listFilesRecursively(cookedContentDir)):
                                cookedContentPaths.append(path)
                                assetPathInfo = getAssetStemPathInfo(path)
                                if assetPathInfo:
                                    if assetPathInfo['stemPath'] not in cookedContentAssetPathsMap:
                                        cookedContentAssetPathsMap[assetPathInfo['stemPath']] = []
                                        if self.debug:
                                            sprint(f'Asset {len(cookedContentAssetPathsMap)}: {assetPathInfo["stemPath"]}')
                                    cookedContentAssetPathsMap[assetPathInfo['stemPath']].append(assetPathInfo['suffix'])
                                    if assetPathInfo['stemPath'] not in assetStemPathSourceFilesMap:
                                        assetStemPathSourceFilesMap[assetPathInfo['stemPath']] = {
                                            'contentDir': cookedContentDir,
                                            'fileSuffixes': cookedContentAssetPathsMap[assetPathInfo['stemPath']],
                                        }

                                if self.debug:
                                    sprint(f'{pathIndex + 1} - {path}')
                            sprint(f'Done reading. Discovered {len(cookedContentAssetPathsMap)} cooked assets ({len(cookedContentPaths)} files)')
                            sprintPad()
                        else:
                            self.printError(f'Cooked content folder "{cookedContentDir}" does not exist')
                            cookedContentDir = ''

            if (inspecting and customizationItemDbPath) or extractingAttachments or upgradingMods or mixingAttachments:
                sprintPad()
                sprint(f'Resolving {CustomizationItemDbAssetName} path...')

                customizationItemDbPathUnaltered = customizationItemDbPath
                customizationItemDbPathIsWildcard = False

                # TODO: fully support standard glob syntax
                wildcardSuffix = '**/CustomizationItemDB'
                if customizationItemDbPath.endswith(wildcardSuffix):
                    customizationItemDbPathIsWildcard = True

                customizationItemDbPath = getPathInfo(customizationItemDbPath)['normalized']
                if not customizationItemDbPath:
                    if extractingAttachments or upgradingMods or mixingAttachments:
                        message = 'Missing or invalid `customizationItemDbPath`'
                        if customizationItemDbPathUnaltered:
                            self.printError(message)
                        else:
                            self.printWarning(message)
                else:
                    customizationItemDbContentDirRelativePath = getContentDirRelativePath(customizationItemDbPath)
                    if customizationItemDbContentDirRelativePath is None:
                        if customizationItemDbPathIsWildcard:
                            self.printError(f'Wildcard `customizationItemDbPath` must be a content folder relative path')
                        else:
                            sprint(f'Done resolving. Resolved path: "{customizationItemDbPath}"')
                            customizationItemDbAssets.append({
                                'path': customizationItemDbPath,
                            })
                    else:
                        sprintPad()
                        sprint(f'Content folder relative path detected: "{customizationItemDbPathUnaltered}"')
                        sprintPad()

                        if not getPathInfo(customizationItemDbContentDirRelativePath)['suffixLower']:
                            customizationItemDbContentDirRelativePath = f'{customizationItemDbContentDirRelativePath}{UassetFilenameSuffix}'
                            sprint(f'Adding "{UassetFilenameSuffix}" suffix: "{customizationItemDbContentDirRelativePath}"')
                            sprintPad()

                        allowTryingAsNormalPath = False

                        if not customizationItemDbAssets and srcPakPath:
                            if srcPakContentDir:
                                customizationItemDbPath = getPathInfo(os.path.join(srcPakContentDir, customizationItemDbContentDirRelativePath))['best']
                                if customizationItemDbPathIsWildcard:
                                    matchingFiles = [getPathInfo(p)['normalized'] for p in glob.glob(customizationItemDbPath, recursive=True)]
                                    sprintPad()
                                    sprint(f'CustomizationItemDB wildcard matches ({len(matchingFiles)}):')
                                    for i, filePath in enumerate(matchingFiles):
                                        sprint(f'{i + 1} - {filePath}')
                                    sprintPad()
                                    if matchingFiles:
                                        for matchingFile in matchingFiles:
                                            customizationItemDbAssets.append({
                                                'path': matchingFile,
                                                'contentDirRelativePath': getPathInfo(
                                                    getPathInfo(matchingFile)['absolute'],
                                                    relativeDir=srcPakContentDir,
                                                )['relative'],
                                            })
                                    else:
                                        self.printWarning('No CustomizationItemDB wildcard matches')
                                elif not os.path.exists(customizationItemDbPath):
                                    self.printWarning(f'Content dir relative path "{customizationItemDbPath}" does not exist')
                            else:
                                message = 'Content folder relative path cannot be resolved because `srcPakPath` is missing content'
                                if allowTryingAsNormalPath:
                                    self.printWarning(message)
                                else:
                                    self.printError(message)
                        elif customizationItemDbPathIsWildcard:
                            # TODO: support other kind of sources, and especially if source asset is in destPakAssets
                            self.printError('CustomizationItemDB wildcard currently only supported for `srcPakPath` source assets')
                        else:
                            if not customizationItemDbAssets and extraContentDir:
                                customizationItemDbPath = getPathInfo(os.path.join(extraContentDir, customizationItemDbContentDirRelativePath))['best']
                                if os.path.exists(customizationItemDbPath):
                                    customizationItemDbAssets.append({
                                        'path': customizationItemDbPath,
                                        'contentDirRelativePath': customizationItemDbContentDirRelativePath,
                                    })
                                else:
                                    self.printWarning(f'Extra content dir relative path "{customizationItemDbPath}" does not exist')

                            if not customizationItemDbAssets and unrealProjectDir:
                                if cookedContentDir:
                                    customizationItemDbPath = getPathInfo(os.path.join(cookedContentDir, customizationItemDbContentDirRelativePath))['best']
                                    if os.path.exists(customizationItemDbPath):
                                        customizationItemDbAssets.append({
                                            'path': customizationItemDbPath,
                                            'contentDirRelativePath': customizationItemDbContentDirRelativePath,
                                        })
                                    else:
                                        self.printWarning(f'Content dir relative path "{customizationItemDbPath}" does not exist')
                                else:
                                    message = 'Content folder relative path cannot be resolved because `unrealProjectDir` is missing content'
                                    if allowTryingAsNormalPath:
                                        self.printWarning(message)
                                    else:
                                        self.printError(message)

                        if len(customizationItemDbAssets):
                            sprint(f'Done resolving. Resolved paths ({len(customizationItemDbAssets)}):')
                            for i, asset in enumerate(customizationItemDbAssets):
                                sprint(f'{i + 1} - {asset["path"]}')
                            sprintPad()
                        elif allowTryingAsNormalPath:
                            self.printWarning(f'Trying `customizationItemDbPath` as normal file path "{customizationItemDbPath}"')
                            customizationItemDbAssets.append({
                                'path': customizationItemDbPathUnaltered,
                            })

                        if not customizationItemDbAssets and not customizationItemDbPathIsWildcard:
                            self.printError(f'Failed to resolve `customizationItemDbPath` "{customizationItemDbPathUnaltered}"')

            assetsCopy = customizationItemDbAssets.copy()
            customizationItemDbAssets = []
            for asset in assetsCopy:
                customizationItemDbPath = asset['path']
                customizationItemDbPathInfo = getPathInfo(customizationItemDbPath)
                customizationItemDbSupportedFileTypes = ['.json', UassetFilenameSuffix]
                if customizationItemDbPathInfo['suffixLower'] not in customizationItemDbSupportedFileTypes:
                    self.printError(f'Unsupported file extension for {customizationItemDbPath}: must be one of ({", ".join(customizationItemDbSupportedFileTypes)})')
                elif not os.path.isfile(customizationItemDbPath):
                    self.printWarning(f'`customizationItemDbPath` "{customizationItemDbPath}" does not exist')
                elif customizationItemDbPathInfo['suffixLower'] == '.json':
                    customizationItemDb = self.readUassetDataFromJson(customizationItemDbPath)
                elif customizationItemDbPathInfo['suffixLower'] == UassetFilenameSuffix:
                    usingTempFile = True
                    customizationItemDbJsonStem = f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered"
                    if usingTempFile:
                        with tempFileHelpers.openTemporaryFile(
                            dir=settingsPathInfo['dir'],
                            prefix=f'{customizationItemDbJsonStem}_',
                            suffix='.json',
                            deleteFirst=True,
                        ) as customizationItemDbJsonFile:
                            customizationItemDbJsonPath = getPathInfo(customizationItemDbJsonFile.name)['best']
                            customizationItemDb = self.readDataFromUasset(
                                customizationItemDbPath,
                                customizationItemDbJsonPath,
                                dryRunHere=False,
                            )
                    else:
                        customizationItemDbJsonPath = getPathInfo(
                            os.path.join(
                                settingsPathInfo['dir'],
                                f'{customizationItemDbJsonStem}.json',
                            ),
                        )['best']
                        customizationItemDb = self.readDataFromUasset(
                            customizationItemDbPath,
                            customizationItemDbJsonPath,
                            dryRunHere=False,
                        )
                else:
                    raise ValueError('internal error')

                if customizationItemDb:
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
                            # TODO: make path unique if writing multiple CustomizationItemDB assets
                            f"{settingsPathInfo['stem']}_{customizationItemDbPathInfo['stem']}-unaltered.yaml",
                        ))['best']
                        sprintPad()
                        sprint(f'{self.dryRunPrefix}Writing unaltered {CustomizationItemDbAssetName} to "{outPath}"...')
                        shouldWrite = not self.dryRun
                        written = False
                        if shouldWrite:
                            if self.readyToWrite(outPath, overwrite=True, dryRunHere=False):
                                with open(outPath, 'w', encoding='utf-8') as file:
                                    yamlDump(customizationItemDb, file)
                                    written = True
                        if written or self.dryRun:
                            sprint(f'{self.dryRunPrefix if not written else ""}Done writing.')
                        sprintPad()

                    customizationItemDbAssets.append(asset)
                    asset['pathInfo'] = customizationItemDbPathInfo
                    # TODO: optmize memory usage by not storing each table data in this list - read each one on the fly when needed for processing
                    asset['data'] = customizationItemDb

            if inspecting or mixingAttachments or renamingAttachmentFiles:
                sprintPad()
                sprint(f'Reading attachments...')
                attachmentFilenames = os.listdir(self.attachmentsDir) if os.path.isdir(self.attachmentsDir) else []
                sprint(f'Done reading. Discovered {len(attachmentFilenames)} attachment files')
                sprintPad()
                if len(attachmentFilenames):
                    for filenameIndex, filename in enumerate(attachmentFilenames):
                        filePath = getPathInfo(os.path.join(self.ensureAttachmentsDir(), filename))['best']
                        try:
                            if filename.endswith('.yaml') or filename.endswith('.json'):
                                with oneLinePrinter() as printOneLine:
                                    printOneLine(f'{filenameIndex + 1} - Reading {filename}...')
                                    with open(filePath, 'r', encoding='utf-8') as file:
                                        if filename.endswith('.yaml'):
                                            attachmentData = yaml.safe_load(file)
                                        elif filename.endswith('.json'):
                                            attachmentData = json.load(file)
                                        else:
                                            raise ValueError(f'Invalid file type: {filename}')

                                    attachmentName = attachmentData['attachmentId']
                                    printOneLine(f'Loaded {attachmentName}.')

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
                                    self.printWarning(f'duplicate attachment {attachmentName}!')

                                if categoryName not in attachmentsToMix:
                                    attachmentsToMix[categoryName] = {}
                                attachmentsToMix[categoryName][attachmentName] = attachmentData

                                if renamingAttachmentFiles:
                                    newFilename = getAttachmentFilename(attachmentName)
                                    if newFilename == filename:
                                        sprint(f'Rename not needed (already named correctly)')
                                    else:
                                        sprint(f'{self.dryRunPrefix}Renaming "{filename}" to "{newFilename}"...')
                                        newFilePath = getPathInfo(os.path.join(self.ensureAttachmentsDir(), newFilename))['best']
                                        if os.path.exists(newFilePath):
                                            raise ValueError(f'Could not rename {filename} to {newFilename} (file already exists)')

                                        if not self.dryRun:
                                            os.rename(filePath, newFilePath)
                                        attachmentsRenamed[filename] = newFilename
                                        sprint('Done renaming.')
                        except Exception as e:
                            self.printError(e)
                    sprint('Done loading attachments.')
                    sprintPad()

                if mixingAttachments or inspecting:
                    sprintPad()
                    sprint('Generating exclusion rules...')
                    sprintPad()

                    setEqualitySymbol = '=='
                    modelRestrictSymbol = ':'
                    modelRestrictSeparator = ','

                    if self.debug:
                        sprintPad()
                        sprint('Reading combosRequired...')

                    def logRequiredSkip(combo, baseModels=None, category=None, isExact=False, info=''):
                        if baseModels is None:
                            baseModels = []
                        def mySorted(combo):
                            if False:
                                return sorted([n for n in combo])
                            return combo
                        sprint(f"require {f'{category} ' if (category and False) else ''}combo {'=' if isExact else '⊇'} {','.join(mySorted(combo)) or '()'}: {','.join(baseModels) or '*'}{f' ({info})' if info else ''}")

                    for category, combosList in combosRequired.items():
                        if category not in categoryCombinationSubsetsRequired:
                            categoryCombinationSubsetsRequired[category] = {}

                        if category not in categoryCombinationsRequired:
                            categoryCombinationsRequired[category] = {}

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

                                if actualAttachment:
                                    checkAttachmentName(category, actualAttachment, f'combosRequired[{comboIndex}][{attachmentIndex}]')
                                    newCombo.add(actualAttachment)

                            frozenCombo = frozenset(newCombo)
                            if isSubset:
                                categoryCombinationSubsetsRequired[category][frozenCombo] = frozenset(baseModels)
                            else:
                                categoryCombinationsRequired[category][frozenCombo] = frozenset(baseModels)
                            if self.debug:
                                logRequiredSkip(frozenCombo, baseModels, isExact=not isSubset, category=category)

                    if self.debug:
                        sprintPad()
                        sprint('Reading combosToSkip...')

                    def logSkip(combo, baseModels=None, category=None, isExact=False, info=''):
                        if baseModels is None:
                            baseModels = []
                        def mySorted(combo):
                            if False:
                                return sorted([n for n in combo])
                            return combo
                        sprint(f"skip {f'{category} ' if (category and False) else ''}combo {'=' if isExact else '⊇'} {','.join(mySorted(combo)) or '()'}: {','.join(baseModels) or '*'}{f' ({info})' if info else ''}")

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

                                if actualAttachment:
                                    checkAttachmentName(category, actualAttachment, f'combosToSkip[{comboIndex}][{attachmentIndex}]')
                                    newCombo.add(actualAttachment)

                            frozenCombo = frozenset(newCombo)
                            if isSubset:
                                categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset(baseModels)
                            else:
                                categoryCombinationsToSkip[category][frozenCombo] = frozenset(baseModels)
                            if self.debug:
                                logSkip(frozenCombo, baseModels, isExact=not isSubset, category=category)

                    if self.debug:
                        sprintPad()
                        sprint('Reading mutuallyExclusive...')

                    for category, groups in mutuallyExclusive.items():
                        if category not in categoryCombinationSubsetsToSkip:
                            categoryCombinationSubsetsToSkip[category] = {}

                        for groupIndex, attachments in enumerate(groups):
                            attachmentsSeen = set()
                            for attachmentIndex, attachment in enumerate(attachments):
                                if attachment in attachmentsSeen:
                                    self.printWarning(f'duplicate attachment ID (mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}])')
                                else:
                                    checkAttachmentName(category, attachment, f'mutuallyExclusive.{category}[{groupIndex}][{attachmentIndex}]')
                                    attachmentsSeen.add(attachment)

                            for duo in combinations(set(attachments), 2):
                                frozenDuo = frozenset(duo)
                                categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                                if self.debug:
                                    logSkip(frozenDuo, category=category)

                    if self.debug:
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
                                    self.printWarning(f'duplicate attachment ID (attachmentConflicts.{category}.{attachment}[{conflictIndex}])')
                                else:
                                    checkAttachmentName(category, conflict, f'attachmentConflicts.{category}.{attachment}[{conflictIndex}]')
                                    frozenDuo = frozenset({attachment, conflict})
                                    categoryCombinationSubsetsToSkip[category][frozenDuo] = frozenset()
                                    if self.debug:
                                        logSkip(frozenDuo, category=category)
                                    attachmentsSeen.add(conflict)

                    if self.debug:
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
                                    self.printWarning(f'duplicate group (equivalentParts.{category}.{equivalent}[{groupIndex}])')
                                    continue

                                # TODO: allow group to map to multiple equivalents?
                                comboEquivalentMap[frozenParts] = equivalent

                                if category not in categoryCombinationSubsetsToSkip:
                                    categoryCombinationSubsetsToSkip[category] = {}

                                partsSeen = set()
                                for partIndex, part in enumerate(parts):
                                    if part in partsSeen:
                                        self.printWarning(f'duplicate part (equivalentParts.{equivalent}[{groupIndex}][{partIndex}])')
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
                                                    if self.debug:
                                                        logSkip(frozenCombo, baseModels, category=category)

                                        # don't allow combos that contain both an attachment and one or more of its parts
                                        frozenCombo = frozenset({equivalent, part})
                                        categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                                        if self.debug:
                                            logSkip(frozenCombo, category=category)
                                        partsSeen.add(part)

                    if self.debug:
                        sprintPad()
                        sprint('Reading supersetParts...')

                    for category, attachmentProperSubsetsMap in supersetParts.items():
                        for attachment, properSubsets in attachmentProperSubsetsMap.items():
                            checkAttachmentName(category, attachment, f'supersetParts->superset')
                            for groupIndex, parts in enumerate(properSubsets):
                                properSubset = frozenset(parts)

                                if True:
                                    if categoryComboEquivalentMap.get(category, {}).get(properSubset, None) == attachment:
                                        self.printWarning(f"proper subset ({properSubset}) is also a perfect subset of {attachment}")
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
                                                if self.debug:
                                                    logSkip(frozenCombo, baseModels, category=category, info=f"{attachment} ⊃ {part}...{','.join(comboToSkip)}")

                                    # don't allow combos that contain both an attachment and one or more of its proper subset parts
                                    frozenCombo = frozenset({attachment, part})
                                    categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                                    if self.debug:
                                        logSkip(frozenCombo, category=category)

                    if self.debug:
                        sprintPad()
                        sprint('Excluding equivalent combos...')

                    for category, comboEquivalentMap in categoryComboEquivalentMap.items():
                        if category not in categoryCombinationSubsetsToSkip:
                            categoryCombinationSubsetsToSkip[category] = {}

                        for frozenCombo in comboEquivalentMap.keys():
                            # don't allow combos containing all the parts of an entire equivalent attachment - use the equivalent instead
                            categoryCombinationSubsetsToSkip[category][frozenCombo] = frozenset()
                            if self.debug:
                                logSkip(frozenCombo, category=category)

                    sprintPad()
                    sprint('Exclusion rules generated.')
                    sprintPad()

                    if self.debug:
                        sprintPad()
                        sprint('categoryCombinationSubsetsToSkip:')
                        sprintPad()
                        sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationSubsetsToSkip))}')
                        sprintPad()
                        sprint('categoryCombinationsToSkip:')
                        sprintPad()
                        sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationsToSkip))}')
                        sprintPad()
                        sprint('categoryCombinationSubsetsRequired:')
                        sprintPad()
                        sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationSubsetsRequired))}')
                        sprintPad()
                        sprint('categoryCombinationsRequired:')
                        sprintPad()
                        sprint(f'{yamlDump(jsonifyDataRecursive(categoryCombinationsRequired))}')
                        sprintPad()

            if (inspecting or extractingAttachments or upgradingMods or mixingAttachments) and customizationItemDbAssets:
                checkInput = self.startKeyboardListener()
                try:
                    for asset in customizationItemDbAssets:
                        self.processCustomizationItemDb(
                            asset,
                            inspecting,
                            upgradingMods,
                            mixingAttachments,
                            extractingAttachments,
                            attachmentsCreated,
                            attachmentsToMix,
                            categoryCombinationsToSkip,
                            categoryCombinationSubsetsToSkip,
                            categoryCombinationsRequired,
                            categoryCombinationSubsetsRequired,
                            settingsPathInfo,
                            assetStemPathSourceFilesMap,
                            writingAlteredDb=True,
                            checkInput=checkInput,
                        )
                finally:
                    self.stopKeyboardListener()

            if paking or inspecting:
                sprintPad()
                sprint(f'Analyzing target pak configuration...')
                if destPakNumber >= 0 or destPakName or destPakAssets is not None or srcPakNumber >= 0:
                    if destPakNumber < 0 and srcPakNumber >= 0:
                        destPakNumber = srcPakNumber
                        self.printWarning(f'Setting `destPakNumber` to "{destPakNumber}" from `srcPakPath`')
                        if srcPakName != destPakName:
                            destPakName = srcPakName
                            self.printWarning(f'Setting `destPakName` to "{destPakName}" from `srcPakPath`')

                    if destPakNumber < 0 and paking:
                        self.printError('Missing or invalid `destPakNumber`')

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
                                self.printError(message)
                            else:
                                self.printWarning(message)

                        destPakFilename = f'{destPakStem}{PakchunkFilenameSuffix}'
                        destPakPath = getPathInfo(os.path.join(ensurePakingDir(), destPakFilename))['best']

                    if destPakAssets is None:
                        if srcPakPath:
                            sprintPad()
                            destPakAssets = [getPathInfo(p)['normalized'] for p in srcPakContentAssetPathsMap.keys()]
                            self.printWarning('Setting `destPakAssets` from `srcPakPath`')
                        else:
                            destPakAssets = []

                    if not destPakAssets:
                        self.printWarning(f'Zero assets configured for paking (empty `destPakAssets`)')

                    shouldSearchForSrcAssets = True

                    # TODO: remove this - because a pak could potentially have zero files in it
                    if not assetStemPathSourceFilesMap and False:
                        message = 'Missing source content folder for paking'
                        if paking:
                            self.printError(message)
                            shouldSearchForSrcAssets = False
                        else:
                            self.printWarning(message)

                    if shouldSearchForSrcAssets:
                        sprintPad()
                        sprint(f'Searching source content folders for {len(destPakAssets)} assets to pak...')

                        srcAssetCount = 0
                        srcFileCount = 0

                        def assetIsMissingMainFile(asset):
                            suffixes = assetStemPathSourceFilesMap[asset]['fileSuffixes']
                            return (
                                (
                                    UexpFilenameSuffix in suffixes
                                    or UbulkFilenameSuffix in suffixes
                                    or UfontFilenameSuffix in suffixes
                                )
                                and UassetFilenameSuffix not in suffixes
                                and UmapFilenameSuffix not in suffixes
                            )

                        shouldFailIfMissingMainFile = True
                        shouldWarnIfMissingMainFile = True

                        missingAssets = False
                        for asset in destPakAssets:
                            if (
                                asset not in assetStemPathSourceFilesMap
                                or (shouldFailIfMissingMainFile and assetIsMissingMainFile(asset))
                            ):
                                missingAssets = True
                                message = f'Missing asset "{asset}" from source content folders'
                                if paking:
                                    self.printError(message)
                                else:
                                    self.printWarning(message)
                            else:
                                if not shouldFailIfMissingMainFile and shouldWarnIfMissingMainFile and assetIsMissingMainFile(asset):
                                    self.printWarning(f'Missing accompanying {UassetFilenameSuffix} or {UmapFilenameSuffix} from source content folders asset "{asset}"')
                                sourceFilesInfo = assetStemPathSourceFilesMap[asset]
                                srcAssetCount += 1
                                srcFileCount += len(sourceFilesInfo['fileSuffixes'])
                                if sourceFilesInfo['contentDir'] not in sourceDirDestAssetsMap:
                                    sourceDirDestAssetsMap[sourceFilesInfo['contentDir']] = []
                                sourceDirDestAssetsMap[sourceFilesInfo['contentDir']].append(asset)

                        sprint(f'Done searching. Found {srcAssetCount} assets ({srcFileCount} files).')
                        sprintPad()

                        if paking and not missingAssets and not self.exitCode:
                            if not destPakContentDir:
                                self.printError(f'Cannot create pak because destination content folder is missing')
                            else:
                                assert destPakDir
                                sprintPad()
                                sprint(f'{self.dryRunPrefix}Copying {srcFileCount} files from source content folders to "{destPakContentDir}"...')
                                ensurePakingDir()
                                sameDir = srcPakDir == destPakDir
                                if sameDir:
                                    self.printWarning(f'Source and destination pak folder is the same. {self.dryRunPrefix}Files not in asset list will be removed.')
                                if self.readyToWrite(destPakDir, delete=not sameDir):
                                    def writeFiles(srcContentDir=None):
                                        self.ensureDir(destPakContentDir, warnIfNotExist=False)
                                        for assetPath in destPakAssets:
                                            srcFilesInfo = assetStemPathSourceFilesMap[assetPath]
                                            fileSuffixes = srcFilesInfo['fileSuffixes']
                                            if UassetFilenameSuffix in fileSuffixes:
                                                fileSuffixes = [UassetFilenameSuffix] + [s for s in fileSuffixes if s != UassetFilenameSuffix]

                                            assetSourceContentDir = assetStemPathSourceFilesMap[assetPath]['contentDir']
                                            if assetSourceContentDir == destPakContentDir:
                                                assetSourceContentDir = srcContentDir

                                            for extension in fileSuffixes:
                                                relFilePath = f'{assetPath}{extension}'
                                                srcPath = normPath(os.path.join(assetSourceContentDir, relFilePath))

                                                # if UassetGUI json file exists, convert it to uasset file before copying it
                                                if extension == UassetFilenameSuffix:
                                                    relJsonFilePath = f'{assetPath}{UassetJsonSuffix}'
                                                    srcJsonPath = normPath(os.path.join(assetSourceContentDir, relJsonFilePath))
                                                    if os.path.exists(srcJsonPath):
                                                        sprintPad()
                                                        sprint(f'{self.dryRunPrefix}Converting "{srcJsonPath}" to "{srcPath}"')
                                                        sprintPad()
                                                        if self.readyToWrite(srcPath):
                                                            if not self.dryRun:
                                                                jsonToUasset(srcJsonPath, srcPath, self.uassetGuiPath)

                                                destPathFileInfo = getPathInfo(os.path.join(destPakContentDir, relFilePath))
                                                self.ensureDir(destPathFileInfo['dir'], warnIfNotExist=False)
                                                destPath = destPathFileInfo['best']
                                                if self.debug:
                                                    sprintPad()
                                                    sprint(f'{self.dryRunPrefix}Copying file "{srcPath}" to "{destPath}"')
                                                    sprintPad()
                                                if not self.dryRun:
                                                    shutil.copy(srcPath, destPath)
                                    if sameDir:
                                        with tempfile.TemporaryDirectory(
                                            dir=pakingDir,
                                            prefix=f'{destPakStem}_',
                                        ) as tempDir:
                                            self.printWarning(f'{self.dryRunPrefix}Temporarily moving "{srcPakDir}" to temporary source pak folder "{tempDir}" for file copying')
                                            if not self.dryRun:
                                                os.rmdir(tempDir)
                                                shutil.move(srcPakDir, tempDir)
                                            assert gameName
                                            try:
                                                writeFiles(getPakContentDir(tempDir, gameName))
                                            except Exception as e:
                                                if not self.nonInteractive and self.debug:
                                                    self.printError(e)
                                                    promptToContinue(f'to open src content dir "{tempDir}"')
                                                    openFolder(tempDir)
                                                    promptToContinue()
                                                raise e
                                    else:
                                        writeFiles()

                                    assert destPakPath
                                    sprintPad()
                                    sprint(f'{self.dryRunPrefix}Paking "{destPakDir}" into "{destPakPath}"...')
                                    if os.path.exists(unrealPakPath):
                                        # TODO: check readyToWrite()?
                                        if not self.dryRun:
                                            checkInput = self.startKeyboardListener()
                                            try:
                                                unrealPak(destPakDir, destPakPath, unrealPakPath, debug=self.debug, checkInput=checkInput)
                                            finally:
                                                self.stopKeyboardListener()
                                            if sigFilePath:
                                                # TODO: check readyToWrite()?
                                                destSigPath = pakchunkToSigFilePath(destPakPath)
                                                if self.debug:
                                                    sprint(f'Copying "{sigFilePath}" to "{destSigPath}"')
                                                shutil.copy(sigFilePath, pakchunkToSigFilePath(destPakPath))
                                        else:
                                            # simulate creating the pakchunk file
                                            pakingDirPakchunkStems.append(destPakStem)
                                        sprint(f'{self.dryRunPrefix}Done paking.')
                                    else:
                                        self.printError(f'`unrealPakPath` "{unrealPakPath}" does not exist')
                                    sprintPad()
                                sprint(f'{self.dryRunPrefix}Done copying.')
                                sprintPad()
                sprint('Done analyzing.')

            if srcPakDir and srcPakDirWasWritten and not self.debug:
                sprintPad()
                sprint(f'{self.dryRunPrefix}Removing "{srcPakDir}" which was extracted from pakchunk "{srcPakPath}"...')
                shouldWrite = not self.dryRun or (not self.nonInteractive and confirm(f'Remove "{srcPakDir}" despite dry run', pad=True, emptyMeansNo=True))
                written = False
                if shouldWrite:
                    shutil.rmtree(srcPakDir)
                    written = True
                if written or self.dryRun:
                    sprint(f'{self.dryRunPrefix if not written else ""}Done removing.')
                sprintPad()

            if (installingMods and not self.exitCode) or searchingGameAssets or inspecting:
                sprintPad()
                sprint(f'Analyzing mod configuration...')

                # don't do the install if there are errors configuring mods
                skipInstall = not gamePaksDir or self.exitCode > 0

                reservedPakchunksFilenameLower = []
                for refI, pakchunkRefname in enumerate(reservedPakchunks):
                    fullFilename = pakchunkRefnameToFilename(pakchunkRefname)
                    if not fullFilename:
                        self.printError(f'`reservedPakchunks[{refI}] is not a valid pakchunk reference ("{pakchunkRefname})')
                        skipInstall = True
                    else:
                        if self.debug and fullFilename.lower() != pakchunkRefname.lower():
                            sprint(f'Resolved reserved pakchunk reference from "{pakchunkRefname}" to "{fullFilename}"')
                        reservedPakchunksFilenameLower.append(fullFilename.lower())

                allGamePakchunks = []
                if gamePaksDir:
                    sprintPad()
                    sprint(f'Scanning "{gamePaksDir}" for pakchunk files...')
                    loggingReserved = self.debug
                    for relPath in listFilesRecursively(gamePaksDir):
                        relPathInfo = getPathInfo(relPath, gamePaksDir)
                        pakchunkFilenameParts = pakchunkRefnameToParts(relPathInfo['basename'])
                        if pakchunkFilenameParts and pakchunkFilenameParts.get('suffix', None):
                            if pakchunkFilenameParts['suffix'] == PakchunkFilenameSuffix:
                                allGamePakchunks.append(relPath)
                                reserved = relPath.lower() in reservedPakchunksFilenameLower
                                if not reserved:
                                    stem = pakchunkRefnamePartsDictToRefname(pakchunkFilenameParts, addSuffix=False)
                                    relStemPath = getPathInfo(os.path.join(relPathInfo['relativeDir'], stem), gamePaksDir)['relative']
                                    gamePakchunks.append(relStemPath)
                                if not reserved or loggingReserved:
                                    sprint(f'{len(allGamePakchunks if loggingReserved else gamePakchunks)} - {relPath}{" -- RESERVED" if reserved else ""}')
                        else:
                            self.printWarning(f'Non-pakchunk file discovered in Paks folder: "{relPath}"')
                    sprint(f'Done scanning. Discovered {len(allGamePakchunks)} pakchunks ({len(allGamePakchunks) - len(gamePakchunks)} reserved, {len(gamePakchunks)} swappable)')
                    sprintPad()

                allPakingDirPakchunks = []
                sprintPad()
                sprint(f'Scanning "{pakingDir}" for available pakchunks...')
                ensurePakingDir()
                for entry in os.scandir(pakingDir):
                    pakchunkFilenameParts = pakchunkRefnameToParts(entry.name)
                    if pakchunkFilenameParts and pakchunkFilenameParts.get('suffix', None) == PakchunkFilenameSuffix:
                        allPakingDirPakchunks.append(entry.name)
                        stem = pakchunkRefnamePartsDictToRefname(pakchunkFilenameParts, addSuffix=False)
                        if stem not in pakingDirPakchunkStems:
                            pakingDirPakchunkStems.append(stem)
                            sprint(f'{len(pakingDirPakchunkStems)} - {stem}')
                sprint(f'Done scanning. Discovered {len(pakingDirPakchunkStems)} pakchunks')
                sprintPad()
                sprint('Done analyzing.')

                if searchingGameAssets:
                    sprint('Searching game assets...')
                    sprintPad()

                    if searchAssetNameMatchers:
                        searchAssetMatchesFile = tempfile.NamedTemporaryFile(
                            mode='w',
                            encoding='utf-8',
                            dir=settingsFilePathInfo['dir'],
                            prefix=f'searchAssetMatches-{settingsFilePathInfo["stem"]}_',
                            suffix='.yaml',
                            delete=False,
                        )
                        openFiles.append(searchAssetMatchesFile)
                        searchAssetMatchesFile.write('searchAssetMatches:\n')
                        searchAssetMatchesFile.flush()
                        sprint(f'Created search results file: {searchAssetMatchesFile.name}')

                    if searchNameMapNameMatchers:
                        searchNameMapMatchesFile = tempfile.NamedTemporaryFile(
                            mode='w',
                            encoding='utf-8',
                            dir=settingsFilePathInfo['dir'],
                            prefix=f'searchNameMapMatches-{settingsFilePathInfo["stem"]}_',
                            suffix='.yaml',
                            delete=False,
                        )
                        openFiles.append(searchNameMapMatchesFile)
                        searchNameMapMatchesFile.write('searchNameMapMatches:\n')
                        searchNameMapMatchesFile.flush()
                        sprint(f'Created search results file: {searchNameMapMatchesFile.name}')

                    if searchJsonStringMatchers:
                        searchJsonStringMatchesFile = tempfile.NamedTemporaryFile(
                            mode='w',
                            encoding='utf-8',
                            dir=settingsFilePathInfo['dir'],
                            prefix=f'searchJsonStringMatches-{settingsFilePathInfo["stem"]}_',
                            suffix='.yaml',
                            delete=False,
                        )
                        openFiles.append(searchJsonStringMatchesFile)
                        searchJsonStringMatchesFile.write('searchJsonStringMatches:\n')
                        searchJsonStringMatchesFile.flush()
                        sprint(f'Created search results file: {searchJsonStringMatchesFile.name}')

                    if searchBinaryAsciiMatchers:
                        searchBinaryAsciiMatchesFile = tempfile.NamedTemporaryFile(
                            mode='w',
                            encoding='utf-8',
                            dir=settingsFilePathInfo['dir'],
                            prefix=f'searchBinaryAsciiMatches-{settingsFilePathInfo["stem"]}_',
                            suffix='.yaml',
                            delete=False,
                        )
                        openFiles.append(searchBinaryAsciiMatchesFile)
                        searchBinaryAsciiMatchesFile.write('searchBinaryAsciiMatches:\n')
                        searchBinaryAsciiMatchesFile.flush()
                        sprint(f'Created search results file: {searchBinaryAsciiMatchesFile.name}')

                    sprintPad()

                    if gamePaksDir and gameName and self.umodelPath and (unrealPakPath or True):
                        checkInput = self.startKeyboardListener(shouldStartPaused=True)
                        try:
                            for gamePakchunkIndex, gamePakchunkRelPath in enumerate(allGamePakchunks):
                                if not checkInput():
                                    break
                                pakchunkFilename = os.path.basename(gamePakchunkRelPath)
                                pakchunkRelDir = os.path.dirname(gamePakchunkRelPath)
                                pakchunkFilenameParts = pakchunkRefnameToParts(pakchunkFilename)
                                pakchunkStem = pakchunkRefnamePartsDictToRefname(pakchunkFilenameParts, addSuffix=False)
                                pakchunkPath = normPath(os.path.join(gamePaksDir, pakchunkRelDir, pakchunkFilename))
                                pakchunkRelStemPath = normPath(os.path.join(pakchunkRelDir, pakchunkStem))
                                if prevSearchResume is not None and prevSearchResume.get('pakchunkRelStemPath', None) and pakchunkRelStemPath != prevSearchResume['pakchunkRelStemPath']:
                                    continue
                                if prevSearchResume:
                                    prevSearchResume['pakchunkRelStemPath'] = None
                                searchResume['pakchunkRelStemPath'] = pakchunkRelStemPath

                                if searchPakchunkNameMatchers:
                                    # TODO: support case sensitive match?
                                    matches = [m for m in searchPakchunkNameMatchers if m.lower() in pakchunkRelStemPath.lower()]
                                    if not matches:
                                        continue

                                with tempfile.TemporaryDirectory(
                                    dir=pakingDir,
                                    prefix=f'{pakchunkStem}_',
                                ) as tempDir:
                                    tempDirPathInfo = getPathInfo(tempDir)
                                    pakchunkCopiedPath = normPath(os.path.join(tempDir, pakchunkFilename))
                                    sprintPad()
                                    sprint(f'Searching pakchunk {gamePakchunkIndex + 1}/{len(allGamePakchunks)}: {pakchunkRelStemPath}...')
                                    sprintPad()
                                    shutil.copy(pakchunkPath, pakchunkCopiedPath)
                                    # TODO: remove
                                    if False:
                                        sprint('Listing package contents')
                                    totalFileCount = None
                                    mountPoint = None
                                    version = None
                                    assetsSeenCount = 0
                                    for streamName, line, stop in runUmodelCommand(
                                        self.umodelPath,
                                        [
                                            arg for arg in [
                                                # Displays Class Statistics (counts of each class). Less output than -list.
                                                f'-pkginfo' if True else None,
                                                # Lists each class instance.
                                                # Without this or -dump or -pkginfo, all viewable object will be displayed in GUI.
                                                f'-list' if False else None,
                                                # Gives detailed object information for supported objects (textures, meshes, materials, etc.).
                                                # Has more output than -pkginfo and -list.
                                                f'-dump' if False else None,
                                                f'-game={self.getUmodelGameTag()}',
                                                f'-path={tempDirPathInfo["absolute"]}',
                                                f'*{UassetFilenameSuffix}',
                                            ] if arg
                                        ],
                                        cwd=tempDirPathInfo['absolute'],
                                        debug=self.debug,
                                    ):
                                        # TODO: remove
                                        if False:
                                            sprint(line)
                                        if not checkInput():
                                            stop()
                                        else:
                                            if streamName == 'return_code':
                                                if line:
                                                    self.printError(f'Command returned error code: {line}')
                                            elif streamName == 'stdout':
                                                if totalFileCount is None and line.startswith('Pak '):
                                                    totalFileCount = 0
                                                    try:
                                                        endPartToken = '.pak: '
                                                        endPartIndex = line.index(endPartToken)
                                                        endPart = line[endPartIndex + len(endPartToken):]
                                                        endParts = endPart.split(', ')
                                                        filesParts = endParts[0].split()
                                                        totalFileCount = int(filesParts[0])
                                                        endParts.pop(0)
                                                        if len(endParts) == 2:
                                                            mountPointParts = endParts[0].split()
                                                            mountPoint = mountPointParts[1]
                                                            endParts.pop(0)
                                                        versionParts = endParts[0].split()
                                                        version = int(versionParts[1])
                                                    except Exception as e:
                                                        self.printError(e)
                                                        self.printError(line)

                                                loadingPrefix = 'Loading package: '
                                                if line.startswith(loadingPrefix):
                                                    assetsSeenCount += 1
                                                    if assetsSeenCount == 1 or assetsSeenCount % 1000 == 0:
                                                        sprint(f'(searched {assetsSeenCount}{f"/{totalFileCount}" if totalFileCount else ""} assets)')
                                                    lineParts = line[len(loadingPrefix):].split()
                                                    packagePath = lineParts[0]

                                                    # TODO: process non /Game/ prefixed assets?
                                                    if not packagePath.startswith(AssetPathGamePrefix) and True:
                                                        continue

                                                    # TODO: only for debug
                                                    if self.debug or True:
                                                        if not packagePath.endswith(UassetFilenameSuffix):
                                                            sprintPad()
                                                            sprint(f'Non-asset package: {packagePath}')
                                                            sprintPad()

                                                    assetShortStemPath = getShortenedAssetPath(packagePath)
                                                    assetStem = os.path.basename(assetShortStemPath)
                                                    if prevSearchResume is not None and prevSearchResume.get('assetPath', None) and assetShortStemPath != prevSearchResume['assetPath']:
                                                        continue
                                                    if prevSearchResume:
                                                        prevSearchResume['assetPath'] = None
                                                    searchResume['assetPath'] = assetShortStemPath

                                                    CustomizationItemDbFilename = f'{CustomizationItemDbAssetName}{UassetFilenameSuffix}'
                                                    isCustomizationItemDb = packagePath.endswith(CustomizationItemDbFilename)
                                                    shouldSearchForSlots = self.searchingSlots and isCustomizationItemDb

                                                    if searchAssetNameMatchers or shouldSearchForSlots:
                                                        assetNameMatchers = (searchAssetNameMatchers or []).copy()
                                                        # TODO: remove
                                                        if False:
                                                            if self.searchingSlots:
                                                                assetNameMatchers.append(CustomizationItemDbFilename)
                                                        # TODO: support case insensitive search (.lower())?
                                                        assetNameMatches = {term for term in assetNameMatchers if term in packagePath}
                                                        if shouldSearchForSlots:
                                                            assetNameMatches.add(CustomizationItemDbFilename)
                                                    else:
                                                        assetNameMatchers = None
                                                        assetNameMatches = None

                                                    if not assetNameMatchers or assetNameMatches:
                                                        if assetNameMatches:
                                                            sprintPad()
                                                            sprint(f'{assetsSeenCount}{f"/{totalFileCount}" if totalFileCount else ""} Asset name match ({",".join(assetNameMatches)}): {pakchunkRelStemPath} - {assetShortStemPath}')
                                                            sprintPad()
                                                            if searchAssetMatchesFile is not None:
                                                                result = {}
                                                                result[assetShortStemPath] = {
                                                                    'assetNameMatches': assetNameMatches,
                                                                    'assetPath': assetShortStemPath,
                                                                    'pakchunk': pakchunkRelStemPath,
                                                                }
                                                                appendYamlFileResult(searchAssetMatchesFile, [result])

                                                        if (
                                                            searchBinaryAsciiMatchers
                                                            or searchNameMapNameMatchers
                                                            or searchJsonStringMatchers
                                                            or shouldSearchForSlots
                                                        ):
                                                            try:
                                                                # TODO: handle packages besides *.uasset, for example *.bnk, *.xml, *.json
                                                                saveFilePath = self.saveAsset(
                                                                    tempDirPathInfo['absolute'],
                                                                    tempDirPathInfo['absolute'],
                                                                    assetShortStemPath,
                                                                    silent=True,
                                                                )
                                                            except Exception as e:
                                                                self.printError(e)
                                                                saveFilePath = None

                                                            if saveFilePath and checkInput():
                                                                try:
                                                                    # TODO: remove
                                                                    if False:
                                                                        sprint(f'Searching "{saveFilePath}"...')
                                                                    saveFileDir = os.path.dirname(saveFilePath)

                                                                    if searchBinaryAsciiMatchers:
                                                                        ChunkSize = 4096
                                                                        overlap = len(longestAsciiMatcher) - 1
                                                                        # TODO: remove
                                                                        if False:
                                                                            sprint(f'longest matcher: {longestAsciiMatcher}')
                                                                            sprint(f'overlap: {overlap}')
                                                                        for path in getAssetSplitFilePaths(saveFilePath):
                                                                            suffix = pathlib.Path(path).suffix
                                                                            # TODO: disable searching ubulk?
                                                                            if suffix == UbulkFilenameSuffix and False:
                                                                                continue

                                                                            if not os.path.isfile(path):
                                                                                continue

                                                                            with open(path, 'rb') as file:
                                                                                previousChunkAscii = ''
                                                                                while chunk := file.read(max(ChunkSize, len(longestAsciiMatcher))):
                                                                                    ascii = chunk.decode('ascii', 'ignore')
                                                                                    asciiLower = ascii.lower()
                                                                                    # TODO: remove
                                                                                    if False:
                                                                                        sprint(ascii)
                                                                                    searchAscii = previousChunkAscii + asciiLower
                                                                                    for matcher in searchBinaryAsciiMatchers:
                                                                                        if matcher in searchAscii:
                                                                                            sprintPad()
                                                                                            sprint(f'Found in ascii: {matcher} in {assetShortStemPath}{suffix}')
                                                                                            sprintPad()
                                                                                            if searchBinaryAsciiMatchesFile is not None:
                                                                                                result = {}
                                                                                                result[assetShortStemPath] = {
                                                                                                    'matcher': matcher,
                                                                                                    # TODO: byte number
                                                                                                    'assetNameMatches': assetNameMatches,
                                                                                                    'assetPath': assetShortStemPath,
                                                                                                    'assetSuffix': suffix,
                                                                                                    'pakchunk': pakchunkRelStemPath,
                                                                                                }
                                                                                                appendYamlFileResult(searchBinaryAsciiMatchesFile, [result])

                                                                                    previousChunkAscii = searchAscii[-overlap:]

                                                                    if (
                                                                        searchNameMapNameMatchers
                                                                        or searchJsonStringMatchers
                                                                        or shouldSearchForSlots
                                                                    ):
                                                                        # TODO: if package suffix is *.uasset
                                                                        with tempFileHelpers.openTemporaryFile(
                                                                            saveFileDir,
                                                                            prefix=f'{assetStem}_',
                                                                            suffix='.json',
                                                                            deleteFirst=True,
                                                                        ) as saveFileJsonFile:
                                                                            saveFileJsonPathInfo = getPathInfo(saveFileJsonFile.name)
                                                                            try:
                                                                                assetData = self.readDataFromUasset(
                                                                                    saveFilePath,
                                                                                    saveFileJsonPathInfo['best'],
                                                                                    silent=True,
                                                                                )
                                                                            except Exception as e:
                                                                                assetData = None
                                                                                self.printError(e)

                                                                            if assetData and checkInput(inDataJson=True):
                                                                                if searchNameMapNameMatchers:
                                                                                    matches = {}
                                                                                    for name in assetData[NameMapFieldName]:
                                                                                        # TODO: remove
                                                                                        if False:
                                                                                            sprint(name)
                                                                                        # TODO: support case sensitive search?
                                                                                        nameMapMatches = [m for m in searchNameMapNameMatchers if m.lower() in name.lower()]
                                                                                        if True:
                                                                                            for matcher in nameMapMatches:
                                                                                                if matcher not in matches:
                                                                                                    matches[matcher] = set()
                                                                                                if name not in matches[matcher]:
                                                                                                    matches[matcher].add(name)
                                                                                        # TODO: remove
                                                                                        elif False:
                                                                                            if nameMapMatches:
                                                                                                if name not in matches:
                                                                                                    matches[name] = set()
                                                                                                for matcher in nameMapMatches:
                                                                                                    matches[name].append(matcher)
                                                                                    if matches:
                                                                                        sprintPad()
                                                                                        sprint(f'{assetsSeenCount}{f"/{totalFileCount}" if totalFileCount else ""} NameMap matches ({",".join(set(chain.from_iterable(matches.values())))}): {pakchunkRelStemPath} - {assetShortStemPath}')
                                                                                        sprintPad()
                                                                                        if searchNameMapMatchesFile is not None:
                                                                                            result = {}
                                                                                            result[assetShortStemPath] = {
                                                                                                'nameMapNameMatches': matches,
                                                                                                'assetNameMatches': assetNameMatches,
                                                                                                'assetPath': assetShortStemPath,
                                                                                                'pakchunk': pakchunkRelStemPath,
                                                                                            }
                                                                                            appendYamlFileResult(searchNameMapMatchesFile, [result])

                                                                                if searchJsonStringMatchers:
                                                                                    jsonStringLines = json.dumps(assetData, indent=2).split('\n')
                                                                                    for matcher in searchJsonStringMatchers:
                                                                                        for lineIndex, line in enumerate(jsonStringLines):
                                                                                            # TODO: support case sensitive search?
                                                                                            if matcher.lower() in line.lower():
                                                                                                sprintPad()
                                                                                                sprint(f'Found in asset json: {matcher} in {assetShortStemPath}')
                                                                                                sprintPad()
                                                                                                if searchJsonStringMatchesFile is not None:
                                                                                                    result = {}
                                                                                                    result[assetShortStemPath] = {
                                                                                                        'matcher': matcher,
                                                                                                        'jsonLineNumber': lineIndex + 1,
                                                                                                        'lines': [line],
                                                                                                        'assetNameMatches': assetNameMatches,
                                                                                                        'assetPath': assetShortStemPath,
                                                                                                        'pakchunk': pakchunkRelStemPath,
                                                                                                    }
                                                                                                    appendYamlFileResult(searchJsonStringMatchesFile, [result])

                                                                                if self.searchingSlots and packagePath.endswith(f'{CustomizationItemDbAssetName}{UassetFilenameSuffix}'):
                                                                                    self.processCustomizationItemDb(
                                                                                        {
                                                                                            'data': assetData,
                                                                                            'pathInfo': saveFileJsonPathInfo,
                                                                                        },
                                                                                        searchingGameAssets=True,
                                                                                        extractingAttachments=extractingAttachments,
                                                                                        umodelCwdPathInfo=tempDirPathInfo,
                                                                                        gamePaksDirPathInfo=getPathInfo(gamePaksDir),
                                                                                        checkInput=checkInput,
                                                                                    )
                                                                finally:
                                                                    for path in getAssetSplitFilePaths(saveFilePath):
                                                                        pathlib.Path.unlink(path, missing_ok=True)
                                            elif streamName == 'stderr':
                                                self.printError(f'stderr: {line}')
                                    # TODO: remove
                                    if False:
                                        pakchunkDir = normPath(os.path.join(tempDir, pakchunkStem))
                                        sprint(f'Unpaking "{pakchunkPath}" to temporary folder "{pakchunkDir}"...')
                                        try:
                                            unrealUnpak(pakchunkPath, pakchunkDir, gameName, unrealPakPath, debug=self.debug, checkInput=checkInput)
                                        except Exception as e:
                                            self.printError(e)
                                            continue
                                        sprint('Done unpaking.')

                                        sprint(f'Searching {pakchunkStem} assets...')
                                        for assetIndex, assetRelPath in enumerate(listFilesRecursively(pakchunkDir)):
                                            sprint(f'{assetIndex + 1} - {assetRelPath}')
                                            if not checkInput():
                                                break
                        finally:
                            self.stopKeyboardListener()

                if installingMods or inspecting:
                    sprintPad()
                    sprint(f'Determining target active mod set...')
                    if activeModConfigName:
                        sprintPad()
                        sprint(f'Active config: "{activeModConfigName}"')
                        if activeModConfigName not in modConfigNameGroupsMap:
                            self.printError(f'Mod config "{activeModConfigName}" not found in `modConfigs`')
                            skipInstall = True
                        else:
                            for groupName in modConfigNameGroupsMap[activeModConfigName]:
                                if groupName not in modGroupNamePakchunksMap:
                                    self.printError(f'Mod group "{groupName}" not found in `modGroups`')
                                    skipInstall = True
                                else:
                                    for pakchunkIndex, pakchunkRefname in enumerate(modGroupNamePakchunksMap[groupName]):
                                        pakchunkStem = pakchunkRefnameToFilename(pakchunkRefname, defaultPlatform=destPlatform, addSuffix=False)
                                        modConfigPath = f'groups.{groupName}[{pakchunkIndex}]: {pakchunkStem}'
                                        if pakchunkStem in targetActiveMods:
                                            self.printWarning(f'Already added mod to be active: {modConfigPath}')
                                        else:
                                            targetActiveMods.append(pakchunkStem)
                                            sprint(f'{len(targetActiveMods)} - {modConfigPath}')
                        sprintPad()

                    sprint(f'Target active mods: {len(targetActiveMods)}')
                    sprintPad()

                    sprintPad()
                    sprint(f'Locating pakchunk sources...')
                    if not gamePaksDir:
                        if installingMods:
                            self.printError('Could not resolve game Paks folder')

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
                                self.printError(f'Pakchunk (to install) not found: {pakchunkStem}')
                                skipInstall = True
                                notFoundPakchunks.append(pakchunkStem)
                                source = None

                            if source is not None and self.debug:
                                sprint(f'"{relStemPath}" <- "{source}"')

                        pakchunksToActivate = [p for p in targetActiveMods if p not in gamePakchunks]
                        sprintPad()
                        sprint(f'New pakchunks to activate: {len(pakchunksToActivate)}')
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
                            sprint(f'{self.dryRunPrefix}Ensuring {len(targetActiveMods)} mod(s) active...')
                            for pakchunkRelStemPath in targetActiveMods:
                                source = f'{pakchunkSourceMap[pakchunkRelStemPath]}{PakchunkFilenameSuffix}'
                                pakchunkRelPath = f'{pakchunkRelStemPath}{PakchunkFilenameSuffix}'
                                dest = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                                if not self.dryRun and not os.path.exists(source):
                                    self.printError(f'Mod to be active source file not found "{source}"')
                                elif source != dest and (not os.path.exists(dest) or self.dryRun or not os.path.samefile(source, dest)):
                                    sprintPad()
                                    sprint(f'{self.dryRunPrefix}Moving "{source}" to "[Paks]/{pakchunkRelPath}"...')
                                    if self.readyToWrite(dest):
                                        if not self.dryRun:
                                            shutil.move(source, dest)
                                            sourceSig = pakchunkToSigFilePath(source)
                                            if os.path.isfile(sourceSig):
                                                # TODO: check readyToWrite()?
                                                # TODO: report that the sig is being copied
                                                shutil.move(sourceSig, pakchunkToSigFilePath(dest))
                                        madeChanges = True
                                        sprint(f'{self.dryRunPrefix}Done moving.')
                                        sprintPad()
                                    else:
                                        self.printWarning(f'Not allowed to overwrite "{pakchunkRelPath}"')
                            sprint(f'{self.dryRunPrefix}Done activating.')
                            sprintPad()

                            sprintPad()
                            sprint(f'{self.dryRunPrefix}Deactivating {len(pakchunksToDeactivate)} mod(s)...')
                            for pakchunkRelStemPath in pakchunksToDeactivate:
                                pakchunkStem = os.path.basename(pakchunkRelStemPath)
                                pakchunkFilename = f'{pakchunkStem}{PakchunkFilenameSuffix}'
                                pakchunkRelPath = f'{pakchunkRelStemPath}{PakchunkFilenameSuffix}'
                                source = normPath(os.path.join(gamePaksDir, pakchunkRelPath))
                                dest = normPath(os.path.join(pakingDir, pakchunkFilename))
                                if pakchunkStem in pakingDirPakchunkStems:
                                    sprintPad()
                                    sprint(f'{self.dryRunPrefix}Removing "[Paks]/{pakchunkRelPath}" which is also stored at "{dest}"...')
                                    if self.readyToWrite(source):
                                        if not self.dryRun:
                                            # TODO: remove this because readyToWrite() should have already deleted it
                                            pathlib.Path.unlink(source, missing_ok=True)
                                            sourceSig = pakchunkToSigFilePath(source)
                                            if os.path.isfile(sourceSig):
                                                # TODO: check readyToWrite()?
                                                # TODO: report that the sig is being deleted
                                                pathlib.Path.unlink(sourceSig)
                                        madeChanges = True
                                        sprint(f'{self.dryRunPrefix}Done removing.')
                                        sprintPad()
                                else:
                                    sprintPad()
                                    sprint(f'{self.dryRunPrefix}Moving "{pakchunkRelPath}" to "{dest}"...')
                                    if not self.dryRun:
                                        shutil.move(source, dest)
                                        sourceSig = pakchunkToSigFilePath(source)
                                        if os.path.isfile(sourceSig):
                                            # TODO: check readyToWrite()?
                                            # TODO: report that the sig is being copied
                                            shutil.move(sourceSig, pakchunkToSigFilePath(dest))
                                    madeChanges = True
                                    sprint(f'{self.dryRunPrefix}Done moving.')
                            sprint(f'{self.dryRunPrefix}Done deactivating.')
                            sprintPad()

                            sprint(f'{self.dryRunPrefix}Installation successful{"" if madeChanges else " - no changes made"}.')
                            sprintPad()
        except Exception as e:
            self.printError(e)
        finally:
            for file in openFiles:
                file.close()
            openFiles = []
            searchAssetMatchesFile = None
            searchNameMapMatchesFile = None
            searchJsonStringMatchesFile = None
            searchBinaryAsciiMatchesFile = None

        if (
            inspecting
            or searchingGameAssets
            or extractingAttachments
            or renamingAttachmentFiles
            or creatingAttachments
            or upgradingMods
            or mixingAttachments
            or paking
            or installingMods
        ):
            def customizationItemDbAssetForOutput(asset):
                result = asset.copy()
                result.pop('data', None)
                result.pop('pathInfo', None)
                if not self.debug:
                    result.pop('nameMapAlterations', None)
                    result.pop('combinationsAdded', None)
                return result

            outputInfo = {
                'warnings': self.warnings,
                'errors': self.errors,
                'discoveredSettingsFiles': discoveredSettingsFiles,
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
                'customizationItemDbAssets': [customizationItemDbAssetForOutput(asset) for asset in customizationItemDbAssets],
                'pakingDirPakchunks': pakingDirPakchunkStems,
                'gamePaksDir': gamePaksDir,
                'gamePakchunks': gamePakchunks,
                'targetActiveMods': targetActiveMods,
                'cookedContentDir': cookedContentDir,
                'cookedAssets': list(cookedContentAssetPathsMap.keys()),
                'cookedFiles': cookedContentPaths,
                'extraAssets': list(extraContentAssetPathsMap.keys()),
                'extraFiles': extraContentPaths,
                'sourceDirDestAssets': sourceDirDestAssetsMap,
                'searchResume': searchResume,
            }

            outputInfoFilename = getResultsFilePath(settingsFilePath)
            sprintPad()
            sprint(f'{self.dryRunPrefix}Writing command results to "{outputInfoFilename}"')
            shouldWrite = not self.dryRun or (not self.nonInteractive and confirm(f'write command results "{outputInfoFilename}" despite dry run', pad=True, emptyMeansNo=True))
            written = False
            if shouldWrite:
                # TODO: should we not overwrite result file without confirmation?
                if self.readyToWrite(outputInfoFilename, overwrite=True):
                    with open(outputInfoFilename, 'w', encoding='utf-8') as file:
                        yamlDump(jsonifyDataRecursive(outputInfo), file)
                        written = True
                        self.wroteResults = True
            if written or self.dryRun:
                sprint(f'{self.dryRunPrefix if not written else ""}Done writing.')
            sprintPad()

        if openingGameLauncher and not self.exitCode:
            sprintPad()
            sprint(f'{self.dryRunPrefix}Opening game launcher{" and starting game if not already running" if launcherStartsGame else ""} (exit the launcher to return)...')
            if self.nonInteractive:
                self.printError('Cannot open game launcher in non-interactive mode')
            elif not gameDir:
                self.printError('Missing or invalid `gameDir`')
            elif not self.dryRun:
                warningOfLauncherClearScreen = launcherClearsScreenBuffer and not getSprintIsRecording()
                if (
                    warningOfLauncherClearScreen
                    and self.overwriteOverride is not True
                    and (
                        inspecting
                        or extractingAttachments
                        or renamingAttachmentFiles
                        or creatingAttachments
                        or upgradingMods
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
                        launcherExitCode = openGameLauncher(
                            getPathInfo(gameDir)['best'],
                            startGame=launcherStartsGame,
                            fromMenu=fromMenu,
                            gameVersion=self.gameVersion,
                        )
                        if launcherExitCode:
                            message = f'launcher returned exit code: {launcherExitCode}'
                            self.printError(message)

                        setConsoleTitle(ConsoleTitle)
                        # TODO: remove
                        if False:
                            # clear any last bits of the launcher output left over
                            sprintClear()
                        if launcherClearsScreenBuffer and getSprintIsRecording():
                            replaySprintRecording()
                    except Exception as e:
                        self.printError(e)
                    finally:
                        clearSprintRecording()
            sprintPad()

        return self.exitCode
