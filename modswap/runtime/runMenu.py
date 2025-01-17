import glob
import os
import pathlib
import platform
import shutil
import tempfile

import semver
import yaml

from modswap.helpers.consoleHelpers import (confirm, esprint, promptToContinue,
                                            sprint, sprintClear, sprintPad,
                                            sprintput, sprintSeparator)
from modswap.helpers.gameHelpers import (KnownSupportedGameVersions,
                                         getGameIsRunning,
                                         getGameServerIsRunning)
from modswap.helpers.guiHelpers import getDirectory, getFile
from modswap.helpers.pakHelpers import UnrealPakProgramStem
from modswap.helpers.pathHelpers import getPathInfo
from modswap.helpers.releaseHelpers import (getGithubProjectReleaseUrl,
                                            getLatestReleaseVersion)
from modswap.helpers.settingsHelpers import (DefaultAttachmentsDir,
                                             DefaultPakingDir,
                                             DefaultSettingsPath,
                                             findSettingsFiles,
                                             getEnabledDisabledStr,
                                             getGameProgramName,
                                             getResultsFilePath,
                                             isValidSettingsFilename)
from modswap.helpers.uassetHelpers import UassetGuiProgramStem
from modswap.helpers.umodelHelpers import UmodelProgramStem
from modswap.helpers.windowsHelpers import openFile, openFolder
from modswap.helpers.yamlHelpers import yamlDump
from modswap.metadata.programMetaData import ProgramName, Version
from modswap.runtime.runCommand import (DefaultLauncherStartsGame,
                                        ModSwapCommandRunner,
                                        readSettingsRecursive)


def getYesOrNoStr(flag, allowNone=False):
    if allowNone and flag is None:
        return 'unknown'
    return 'yes' if flag else 'no'


def getOnOrOffStr(flag, allowNone=False):
    if allowNone and flag is None:
        return 'unknown'
    return 'on' if flag else 'off'


def reportAmbigous(token, matchingItems):
    tokenLower = token.lower()

    def highlightedMenuItem(itemName):
        itemNameLower = itemName.lower()
        startIndex = itemNameLower.index(tokenLower)
        firstPart = itemName[:startIndex]
        lastPart = itemName[(startIndex + len(token)):]
        return f"{firstPart}{token.upper()}{lastPart}"

    esprint(f'"{token}" could be {" | ".join([highlightedMenuItem(name) for name, item in matchingItems])}.')
    esprint('Type more of the name.')


def getMenuItemObject(menuItem):
    if isinstance(menuItem, dict):
        return menuItem

    return {
        'name': menuItem,
    }


def parseMenuItemFromToken(token, menuItems, allowExact=True, allowSubset=True, allowCustom=False):
    token = (token or '').strip()
    tokenLower = token.lower()

    result = None

    if tokenLower:
        menuNumberItemMap = {i + 1: item for i, item in enumerate(menuItems)}
        menuAliasLowerItemMap = {}
        menuAliasLowerAliasMap = {}
        for item in menuItems:
            itemObject = getMenuItemObject(item)
            aliases = [itemObject['name']] + itemObject.get('item', {}).get('aliases', [])
            for alias in aliases:
                aliasLower = alias.lower()
                menuAliasLowerItemMap[aliasLower] = item
                menuAliasLowerAliasMap[aliasLower] = alias

        try:
            tokenNumber = int(token)
            if f'{tokenNumber}' != token:
                tokenNumber = None
        except:
            tokenNumber = None

        if not result and tokenNumber is not None:
            result = menuNumberItemMap.get(tokenNumber, None)
        else:
            if not result and allowExact:
                result = menuAliasLowerItemMap.get(tokenLower, None)

            if not result and allowSubset:
                resultMatches = []
                matchItemNames = set()
                for nameLower, item in menuAliasLowerItemMap.items():
                    name = getMenuItemObject(item)['name']
                    if name not in matchItemNames and tokenLower in nameLower:
                        resultMatches.append((menuAliasLowerAliasMap[nameLower], item))
                        matchItemNames.add(name)

                if len(resultMatches) == 1:
                    result = resultMatches[0][1]
                elif len(resultMatches) > 0:
                    result = resultMatches

            if not result and allowCustom:
                result = token

    return result


def runMenu(args, parser):
    menuSettingsPath = '.menu_settings.yaml'
    menuSettings = None

    showingMenu = True
    menuSettingsDirty = False

    def saveMenuSettings():
        try:
            with open(menuSettingsPath, 'w', encoding='utf-8') as file:
                yamlDump(menuSettings, file)
            return True
        except Exception as e:
            sprintPad()
            esprint(e)
            sprintPad()

    sprintClear()

    while True:
        sprint(f'Welcome to {ProgramName}!')

        if menuSettings is None:
            if os.path.isfile(menuSettingsPath):
                try:
                    with open(menuSettingsPath, 'r', encoding='utf-8') as file:
                        menuSettings = yaml.safe_load(file)
                except Exception as e:
                    sprintPad()
                    esprint(e)
                    sprintPad()
            if menuSettings is None:
                menuSettings = {}

        if menuSettings.get('showFirstTimeMessage', True):
            sprintPad()
            sprint(parser.description)
            promptToContinue()
            menuSettings['showFirstTimeMessage'] = False
            saveMenuSettings()
            sprintClear()
            continue

        break

    def printLatestVersionDownloadMessage(latestVersion):
        sprint(f'A new version ({latestVersion}) is available to download at {getGithubProjectReleaseUrl()}')

    latestVersion = getLatestReleaseVersion()
    if latestVersion and semver.compare(Version, latestVersion) < 0:
        sprintPad()
        printLatestVersionDownloadMessage(latestVersion)

    sprintPad()
    sprint('You can run one or more actions at a time by entering menu item numbers or names.')

    exitCode = 0

    settingsFilePath = getPathInfo(args.settingsFile or menuSettings.get('settingsFilePath', DefaultSettingsPath))['best']
    if settingsFilePath != menuSettings.get('settingsFilePath', None):
        menuSettings['settingsFilePath'] = settingsFilePath
        menuSettingsDirty = True
    settingsFileExists = False
    settingsFileValid = False
    settings = {}

    gameDir = (args.gameDir or '').strip() or menuSettings.get('gameDir', None)
    if gameDir:
        gameDir = getPathInfo(gameDir)['best']
    if gameDir != menuSettings.get('gameDir', None):
        menuSettings['gameDir'] = gameDir
        menuSettingsDirty = True

    gameVersion = (args.gameVersion or '').strip() or menuSettings.get('gameVersion', None)
    if gameVersion != menuSettings.get('gameVersion', None):
        menuSettings['gameVersion'] = gameVersion
        menuSettingsDirty = True

    srcPakPath = (args.srcPakPath or '').strip()
    srcPakPaths = []
    if srcPakPath:
        srcPakPaths = glob.glob(srcPakPath)
        if not srcPakPaths:
            srcPakPaths = [srcPakPath]

    customizationItemDbPath = (args.customizationItemDbPath or '').strip()
    prevGameVersion = (args.prevGameVersion or '').strip()

    pakingDir = (args.pakingDir or '').strip() or menuSettings.get('pakingDir', None) or None
    if pakingDir:
        pakingDir = getPathInfo(pakingDir)['best']
    if pakingDir != menuSettings.get('pakingDir', None):
        menuSettings['pakingDir'] = pakingDir
        menuSettingsDirty = True

    attachmentsDir = (args.attachmentsDir or '').strip() or menuSettings.get('attachmentsDir', None) or None
    if attachmentsDir:
        attachmentsDir = getPathInfo(attachmentsDir)['best']
    if attachmentsDir != menuSettings.get('attachmentsDir', None):
        menuSettings['attachmentsDir'] = attachmentsDir
        menuSettingsDirty = True

    unrealProjectDir = (args.unrealProjectDir or '').strip() or menuSettings.get('unrealProjectDir', None)
    if unrealProjectDir:
        unrealProjectDir = getPathInfo(unrealProjectDir)['best']
    if unrealProjectDir != menuSettings.get('unrealProjectDir', None):
        menuSettings['unrealProjectDir'] = unrealProjectDir
        menuSettingsDirty = True

    uassetGuiPath = (args.uassetGuiPath or '').strip() or menuSettings.get('uassetGuiPath', None)
    if uassetGuiPath:
        uassetGuiPath = getPathInfo(uassetGuiPath)['best']
    if uassetGuiPath != menuSettings.get('uassetGuiPath', None):
        menuSettings['uassetGuiPath'] = uassetGuiPath
        menuSettingsDirty = True

    unrealPakPath = (args.unrealPakPath or '').strip() or menuSettings.get('unrealPakPath', None)
    if unrealPakPath:
        unrealPakPath = getPathInfo(unrealPakPath)['best']
    if unrealPakPath != menuSettings.get('unrealPakPath', None):
        menuSettings['unrealPakPath'] = unrealPakPath
        menuSettingsDirty = True

    sigFilePath = (args.sigFile or '').strip() or menuSettings.get('sigFilePath', None)
    if sigFilePath:
        sigFilePath = getPathInfo(sigFilePath)['best']
    if sigFilePath != menuSettings.get('sigFilePath', None):
        menuSettings['sigFilePath'] = sigFilePath
        menuSettingsDirty = True

    umodelPath = (args.umodelPath or '').strip() or menuSettings.get('umodelPath', None)
    if umodelPath:
        umodelPath = getPathInfo(umodelPath)['best']
    if umodelPath != menuSettings.get('umodelPath', None):
        menuSettings['umodelPath'] = umodelPath
        menuSettingsDirty = True

    userSpecifiedModConfigName = (args.activeModConfig or '').strip() or menuSettings.get('activeModConfig', None)
    activeModConfigName = None
    activeModConfigExists = False

    launcherStartsGame = args.autoLaunch if isinstance(args.autoLaunch, bool) else menuSettings.get('launcherStartsGame', None)
    if launcherStartsGame is None:
        launcherStartsGame = DefaultLauncherStartsGame
    if launcherStartsGame is not None and launcherStartsGame != menuSettings.get('launcherStartsGame', None):
        menuSettings['launcherStartsGame'] = launcherStartsGame
        menuSettingsDirty = True

    debug = args.debug or menuSettings.get('debug', False)
    dryRun = args.dryRun or menuSettings.get('dryRun', False)
    overwriteOverride = args.overwrite if args.overwrite is not None else menuSettings.get('overwriteOverride', None)

    getFlagValueStr = getEnabledDisabledStr

    def getValueStr(value):
        return value or '<Not specified>'

    def getFilePathStr(filePath, info=None, quote=None, shorten=None):
        if quote is None:
            quote = True
        if shorten is None:
            shorten = True
        path = filePath
        if path:
            if shorten:
                shortPath = os.path.basename(path)
                if path != shortPath:
                    path = f'.../{shortPath}'
            if quote:
                path = f'"{path}"'

        return getValueStr(f'{path}{f" ({info})" if info else ""}' if path else None)

    def getDirStr(dir, info=None, quote=None, shorten=None):
        # TODO: remove
        if quote is None and False:
            quote = False
        return getFilePathStr(dir, info, quote, shorten)

    def getSettingsFileStr(shorten=None):
        return getFilePathStr(settingsFilePath, (("loaded" if False else "") if settingsFileValid else "invalid") if settingsFileExists else "new file", shorten=shorten)

    def getGameDirStr(shorten=None):
        return getDirStr(gameDir, shorten=shorten)

    def getPakingDirStr(shorten=None):
        return getDirStr(pakingDir, shorten=shorten)

    def getAttachmentsDirStr(shorten=None):
        return getDirStr(attachmentsDir, shorten=shorten)

    def getUnrealProjectDirStr(shorten=None):
        return getDirStr(unrealProjectDir, shorten=shorten)

    def getUassetGuiPathStr(shorten=None):
        return getFilePathStr(uassetGuiPath, shorten=shorten)

    def getUnrealPakPathStr(shorten=None):
        return getFilePathStr(unrealPakPath, shorten=shorten)

    def getSigFilePathStr(shorten=None):
        return getFilePathStr(sigFilePath, shorten=shorten)

    def getUmodelPathStr(shorten=None):
        return getFilePathStr(umodelPath, shorten=shorten)

    def getActiveModConfigStr():
        # TODO: report whether mod config is verified to be installed or not, and whether it matches `activeModConfig` settings
        return getValueStr(f'"{activeModConfigName}"{("" if activeModConfigExists else " (missing)")}' if activeModConfigName else None)

    def getOverwriteModeStr():
        return 'always' if overwriteOverride else 'never' if overwriteOverride is False else 'ask'

    def handleFileChooserResult(currValue, name, result):
        myResult = result
        if not myResult and currValue:
            if not confirm(f'clear path to {name}', prefix='Canceled. ', emptyMeansNo=True, pad=True):
                myResult = currValue
            sprintSeparator()
        return myResult

    def modConfigExists(modConfigName):
        return modConfigName in settings.get('modConfigs', {})

    def readSettings():
        nonlocal settingsFileExists
        nonlocal settingsFileValid
        nonlocal settings
        nonlocal activeModConfigName
        nonlocal activeModConfigExists
        nonlocal menuSettingsDirty

        settingsFileExists = False
        settingsFileValid = False
        settings = {}
        try:
            settingsFileExists = os.path.exists(settingsFilePath)
            if settingsFileExists:
                settingsFileValid = os.path.isfile(settingsFilePath)
                if settingsFileValid:
                    settings = readSettingsRecursive(settingsFilePath, silent=True)
        except:
            settingsFileValid = False

        activeModConfigName = userSpecifiedModConfigName
        if activeModConfigName and modConfigExists(activeModConfigName):
            activeModConfigExists = True
        else:
            activeModConfigName = settings.get('activeModConfig', None)
            activeModConfigExists = modConfigExists(activeModConfigName)
            # TODO: clear userSpecifiedModConfigName?

        if userSpecifiedModConfigName != menuSettings.get('activeModConfig', None):
            menuSettings['activeModConfig'] = userSpecifiedModConfigName
            menuSettingsDirty = True

    actionsMap = {action.dest: action for action in parser._actions}

    mainMenu = {
        'name': 'main',
        'items': [
            {'title': 'Game'},
            {'name': 'modConfig',
             'aliases': ['activeModConfig',
                         'activeConfig',
                         'activeMods',
                         'mods']},
            {'name': 'install'},
            {'name': 'auto', 'hidden': True},
            {'name': 'launch',
             'aliases': ['launcher']},
            {'name': 'kill'},
            {'title': 'Settings'},
            {'name': 'settingsFile'},
            {'name': 'edit'},
            {'name': 'results',
             'aliases': ['commandResults',
                         'commandOutput']},
            {'name': 'folders',
             'aliases': ['dirs',
                         'directory',
                         'directories'],
                'items': [
                    # TODO: add srcPakDir, unrealProjectDir, extraContentDir
                    {'name': 'openSettingsDir'},
                    {'name': 'openGameDir'},
                    {'name': 'openPakingDir',
                     'aliases': ['openPaksDirectory',
                                 'openPaksFolder',
                                 'openPakingDirectory',
                                 'openPakingFolder']},
                    {'name': 'openAttachmentsDir'},
                    {'name': 'back',
                     'aliases': ['return',
                                 'previous']},
                    {'name': 'quit', 'hidden': True,
                     'aliases': ['exit']},
                ],
            },
            {'name': 'moreOptions',
                'items': [
                    {'title': 'Game'},
                    {'name': 'autoLaunch'},
                    {'name': 'gameDir',
                     'aliases': ['gameFolder',
                                 'gameDirectory']},
                    {'name': 'gameVersion'},
                    {'name': 'pakingDir',
                     'aliases': ['paksDirectory',
                                 'paksFolder',
                                 'pakingDirectory',
                                 'pakingFolder']},
                    {'title': 'Modding'},
                    {'name': 'uassetGuiPath'},
                    {'name': 'unrealPakPath'},
                    {'name': 'sigFile'},
                    {'name': 'umodelPath'},
                    {'name': 'unrealProjectDir',
                     'aliases': ['unrealProjectDirectory',
                                 'unrealProjectFolder']},
                    {'name': 'attachmentsDir',
                     'aliases': ['attachmentsDirectory',
                                 'attachmentsFolder',
                                 'socketsFolder',
                                 'socketsDirectory']},
                    {'name': 'upgrade'},
                    {'name': 'back',
                     'aliases': ['return',
                                 'previous']},
                    {'name': 'quit', 'hidden': True,
                     'aliases': ['exit']},
                ],
            },
            {'title': 'Modding'},
            {'name': 'list'},
            {'name': 'sockets',
             'aliases': ['socketing',
                         'socketDefinitions',
                         'socketAttachments',
                         'socketAttachmentDefinitions',
                         'attachments',
                         'attachmentDefinitions'],
                'items': [
                    {'name': 'list',
                     'aliases': ['inspect']},
                    {'name': 'search'},
                    {'name': 'create'},
                    {'name': 'extract'},
                    {'name': 'rename'},
                    {'name': 'results',
                    'aliases': ['commandResults',
                                'commandOutput']},
                    {'name': 'overwrite', 'hidden': True},
                    {'name': 'dryRun', 'hidden': True},
                    {'name': 'debug', 'hidden': True},
                    {'name': 'back',
                     'aliases': ['return',
                                 'previous']},
                    {'name': 'quit', 'hidden': True,
                     'aliases': ['exit']},
                ],
            },
            {'name': 'upgrade', 'hidden': True},
            {'name': 'mix'},
            {'name': 'pak'},
            {'title': 'Flags'},
            {'name': 'overwrite'},
            {'name': 'dryRun'},
            {'name': 'debug'},
            {'title': 'About'},
            {'name': 'version'},
            {'name': 'help'},
            {'name': 'quit',
             'aliases': ['exit']},
        ]
    }

    activeMenu = None
    activeMenuActionNameMap = {}
    activeMenuActions = []
    activeMenuSubMenuMap = {}

    menuStack = []

    def setMenu(menu):
        nonlocal activeMenu
        nonlocal activeMenuActionNameMap
        nonlocal activeMenuSubMenuMap
        nonlocal activeMenuActions

        activeMenuAllObjects = [getMenuItemObject(item) for item in menu['items']]
        activeMenuActionNameItemObjectPairs = [(item['name'], item) for item in activeMenuAllObjects if item.get('name', None)]
        activeMenuSubMenuMap = {item['name']: item for item in activeMenuAllObjects if item.get('items', None)}
        for item in list(activeMenuSubMenuMap.values()):
            for alias in item.get('aliases', []):
                activeMenuSubMenuMap[alias] = item

        activeMenuActionNameMap = {
            actionName: {
                'name': actionName,
                'number': i + 1,
                'item': itemObject,
                'action': actionsMap.get(actionName, None),
            } for i, (actionName, itemObject) in enumerate(activeMenuActionNameItemObjectPairs)
        }
        activeMenuActions = list(activeMenuActionNameMap.values())

        activeMenu = menu

    def pushMenu(menu):
        assert menu
        menuStack.append(menu)
        setMenu(menu)

    def popMenu():
        menuStack.pop()
        setMenu(menuStack[-1])

    pushMenu(mainMenu)

    while True:
        inspecting = False
        searchingGameAssets = False
        creatingAttachments = False
        extractingAttachments = False
        renamingAttachmentFiles = False
        mixingAttachments = False
        paking = False
        installingMods = False
        upgradingMods = False
        openingGameLauncher = False
        killingGame = False

        exitCode = 0

        if not showingMenu:
            showingMenu = True
        else:
            # TODO: only do this when explicitly refreshed
            readSettings()

            showServerRunning = False
            showGameRunning = False
            if showServerRunning:
                gameServerRunning = getGameServerIsRunning()
            if showGameRunning:
                gameProgramName = getGameProgramName(settings)
                if gameProgramName:
                    gameRunning = getGameIsRunning(gameProgramName)
                else:
                    gameRunning = None

            sprintPad()
            # TODO: remove
            if False:
                sprint(f'Settings file: {getSettingsFileStr()}')
                sprint(f'Active mod config: {getActiveModConfigStr()}')
                sprint(f"Overwrite files: {getOverwriteModeStr()}")
                sprint(f"Dry run: {getFlagValueStr(dryRun)}")
                sprint(f"Debug: {getFlagValueStr(debug)}")
            if showServerRunning:
                sprint(f'Game server running: {getYesOrNoStr(gameServerRunning, allowNone=True)}')
            if showGameRunning:
                sprint(f'Game running: {getYesOrNoStr(gameRunning, allowNone=True)}')

            sprintPad()

            for menuItem in activeMenu['items']:
                menuItemObject = getMenuItemObject(menuItem)

                actionName = menuItemObject.get('name', None)
                if not actionName:
                    title = menuItemObject.get('title', '')
                    if title:
                        sprint(f'------------  {title}  ------------')
                    else:
                        sprintPad()
                    continue

                action = activeMenuActionNameMap[actionName]
                value = None
                help = action['action'].help if action['action'] is not None else None
                if actionName == 'help':
                    help = 'show help page'
                elif actionName == 'version':
                    help = "show version"
                elif actionName == 'modConfig':
                    value = getActiveModConfigStr()
                    if True:
                        help = 'the mod config to install'
                elif actionName == 'settingsFile':
                    value = getSettingsFileStr()
                    help = 'the active settings file'
                elif actionName == 'launch':
                    help = f'enter launcher menu{" and start game" if launcherStartsGame else ""}'
                elif actionName == 'quit':
                    # TODO: remove
                    if False:
                        help = "quit program"
                    else:
                        help = None
                elif actionName == 'debug':
                    value = getFlagValueStr(debug)
                    # TODO: remove
                    if False:
                        help = f"turn [{getOnOrOffStr(not debug)}] debug flag ({'do not ' if debug else ''}{action['action'].help})"
                elif actionName == 'dryRun':
                    value = getFlagValueStr(dryRun)
                    # TODO: remove
                    if False:
                        help = f"turn {getOnOrOffStr(not dryRun)} dry flag ({'do not ' if dryRun else ''}{action['action'].help})"
                elif actionName == 'overwrite':
                    value = getOverwriteModeStr()
                    if False:
                        help = f"switch overwrite mode ({action['action'].help})"
                    else:
                        help = 'overwrite existing files'
                elif actionName == 'gameDir':
                    value = getGameDirStr()
                elif actionName == 'gameVersion':
                    value = getValueStr(gameVersion)
                elif actionName == 'pakingDir':
                    value = getPakingDirStr()
                elif actionName == 'attachmentsDir':
                    value = getAttachmentsDirStr()
                elif actionName == 'unrealProjectDir':
                    value = getUnrealProjectDirStr()
                elif actionName == 'autoLaunch':
                    value = getFlagValueStr(launcherStartsGame)
                elif actionName == 'uassetGuiPath':
                    value = getUassetGuiPathStr()
                elif actionName == 'unrealPakPath':
                    value = getUnrealPakPathStr()
                elif actionName == 'sigFile':
                    value = getSigFilePathStr()
                elif actionName == 'umodelPath':
                    value = getUmodelPathStr()
                elif actionName == 'moreOptions':
                    help = 'more options and settings'
                elif actionName == 'folders':
                    help = f'open files and folders'
                elif actionName == 'openSettingsDir':
                    help = 'open settings file folder'
                elif actionName == 'openGameDir':
                    help = 'open game folder'
                elif actionName == 'openPakingDir':
                    help = 'open paking folder'
                elif actionName == 'openAttachmentsDir':
                    help = 'open attachments folder'
                elif actionName == 'edit':
                    help = f'open settings in editor'
                elif actionName == 'results':
                    help = f'open command results in editor'
                elif actionName == 'sockets':
                    help = 'find, create, and extract socket attachment definitions'

                if not menuItemObject.get('hidden', False):
                    valueStr = ('{' + value + '}') if value else ''
                    sprint(f"[ {action['number']} ] {actionName[0].upper()}{actionName[1:]}{f' {valueStr}' if valueStr else ''}{f' - {help}' if help else ''}")
            sprintPad()

        if menuSettingsDirty:
            if saveMenuSettings():
                menuSettingsDirty = False

        sprintPad()
        response = sprintput('Selection: ').strip()
        sprintPad()

        shouldPromptToContinue = False
        showingSeparator = True
        shouldQuit = False
        actions = []

        tokens = response.split()
        hasError = False
        results = [parseMenuItemFromToken(token, activeMenuActions) for token in tokens]

        # TODO: remove
        if False:
            sprintPad()
            sprintP(results)
            sprintPad()

        invalidTokens = []
        ambiguousMap = {}
        for token, result in zip(tokens, results):
            if isinstance(result, dict):
                actions.append(result)
            elif isinstance(result, list):
                ambiguousMap[token] = result
                hasError = True
            else:
                if token not in invalidTokens:
                    invalidTokens.append(token)
                    hasError = True

        if hasError:
            sprintSeparator()
            if invalidTokens:
                sprintPad()
                sprint(f'Invalid token(s): {" | ".join(invalidTokens)}')
                sprintPad()

            if ambiguousMap:
                for token, matchingItems in ambiguousMap.items():
                    sprintPad()
                    reportAmbigous(token, matchingItems)
                    sprintPad()

            actions = []
            showingMenu = False

        if actions:
            shouldRunMain = False

            actionNamesRemaining = {action['name'] for action in actions}

            def popAction(*actionNames):
                for actionName in actionNames:
                    if actionName in actionNamesRemaining:
                        actionNamesRemaining.remove(actionName)
                        return actionName

            def popOpenPathAction(actionName, description, path, isDir=True):
                nonlocal shouldPromptToContinue

                if popAction(actionName):
                    prepActionRun()
                    sprint(f'Opening {description} {"folder" if isDir else "file"}: "{path}"')
                    shouldPromptToContinue = shouldPromptToContinueForExternalApp
                    if platform.system() != 'Windows':
                        sprintSeparator()
                        esprint('Only supported on Windows')
                        shouldPromptToContinue = True
                    else:
                        try:
                            if isDir:
                                openFolder(path)
                            else:
                                openFile(path)
                        except Exception as e:
                            sprintSeparator()
                            esprint(e)
                            sprintPad()
                            shouldPromptToContinue = True
                    sprintPad()

            shouldPromptToContinueForSettings = False
            shouldPromptToContinueForExternalApp = False

            ranPriorAction = False

            def prepActionRun():
                nonlocal ranPriorAction
                nonlocal shouldPromptToContinue
                nonlocal showingSeparator

                sprintSeparator()

                if ranPriorAction:
                    if shouldPromptToContinue:
                        promptToContinue()
                        sprintSeparator()

                ranPriorAction = True
                shouldPromptToContinue = False
                showingSeparator = True

            if popAction('quit'):
                shouldQuit = True

            if popAction('help'):
                prepActionRun()
                sprint(parser.format_help())
                shouldPromptToContinue = True

            if popAction('version'):
                prepActionRun()
                sprint(f'{parser.prog} {Version}')
                latestVersion = getLatestReleaseVersion()
                if latestVersion:
                    if semver.compare(Version, latestVersion) < 0:
                        sprintPad()
                        printLatestVersionDownloadMessage(latestVersion)
                    elif semver.compare(Version, latestVersion) == 0:
                        sprint('Up-to-date.')
                    else:
                        sprintPad()
                        sprint(f'You are currently ahead of the latest release version ({latestVersion}).')
                else:
                    sprintPad()
                    esprint('Could not get latest release version information.')

                shouldPromptToContinue = True

            if popAction('settingsFile'):
                prepActionRun()
                filenames = []
                for filenameIndex, filename in enumerate(findSettingsFiles()):
                    if not len(filenames):
                        sprintPad()
                        sprint('Local settings files: ')
                    sprint(f'[ {filenameIndex + 1} ] - {filename}')
                    filenames.append(filename)
                sprintPad()
                while True:
                    filePath = sprintput(f'Settings YAML file path (enter number or path; enter nothing to open file dialog): ').strip()

                    usingFilePicker = not filePath

                    sprintSeparator()

                    if usingFilePicker:
                        sprint('Opening file browser...')
                        sprintPad()

                        filePath = getPathInfo(getFile(
                            title=f'Choose New or Existing Settings File',
                            initialDir=os.getcwd(),
                            initialFile=settingsFilePath or None,
                            fileTypes=[('YAML', '.yaml')],
                        ) or '')['best']

                    filePath = handleFileChooserResult(settingsFilePath, 'settings file', filePath)

                    if not filePath:
                        filePath = DefaultSettingsPath
                        sprint(f'(using default)')
                        sprintSeparator()
                        break

                    if not usingFilePicker:
                        allowSubset = (
                            filePath[0] not in {'.', '/', '\\'}
                            and not filePath.lower().endswith('.yaml')
                        )
                        inputChoice = parseMenuItemFromToken(filePath, filenames, allowExact=True, allowSubset=allowSubset, allowCustom=True)
                        if not inputChoice:
                            esprint('Invalid option.')
                            sprintSeparator()
                            continue
                        elif isinstance(inputChoice, list):
                            reportAmbigous(filePath, inputChoice)
                            sprintSeparator()
                            continue
                        elif not inputChoice.lower().endswith('.yaml'):
                            esprint('Invalid path (missing ".yaml" file extension)')
                            sprintSeparator()
                            continue
                        else:
                            filePath = getPathInfo(inputChoice)['best']

                    if isValidSettingsFilename(filePath):
                        break
                    else:
                        esprint('Filename not allowed')
                        sprintSeparator()
                        continue

                if settingsFilePath != filePath:
                    settingsFilePath = filePath
                    readSettings()
                    sprint(f'Settings file path set to: {getSettingsFileStr(shorten=False)}')
                else:
                    sprint(f'Settings file path unchanged: {getSettingsFileStr(shorten=False)}')
                if settingsFilePath != menuSettings.get('settingsFilePath', None):
                    menuSettings['settingsFilePath'] = settingsFilePath
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('gameDir'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                dirPath = handleFileChooserResult(gameDir, 'game folder', getPathInfo(getDirectory(
                    title='Select Game Folder',
                    mustExist=True,
                    initialDir=gameDir or os.getcwd(),
                ) or '')['best'])
                if gameDir != dirPath:
                    gameDir = dirPath
                    sprint(f'Game folder set to: {getGameDirStr(shorten=False)}')
                else:
                    sprint(f'Game folder unchanged: {getGameDirStr(shorten=False)}')
                if gameDir != menuSettings.get('gameDir', None):
                    menuSettings['gameDir'] = gameDir
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('gameVersion'):
                prepActionRun()
                value = sprintput(f'Game version: ').strip() or None

                if value:
                    if value not in KnownSupportedGameVersions:
                        sprintPad()
                        sprint(f'Warning: not in the list of known supported versions ({", ".join(KnownSupportedGameVersions)})')
                        sprintSeparator()

                if value != gameVersion:
                    gameVersion = value
                    sprintPad()
                    sprint(f'Game version set to: {getValueStr(gameVersion)}')
                else:
                    sprintPad()
                    sprint(f'Game version unchanged: {getValueStr(gameVersion)}')

                if gameVersion != menuSettings.get('gameVersion', None):
                    menuSettings['gameVersion'] = gameVersion
                    menuSettingsDirty = True

                shouldPromptToContinue = True

            if popAction('pakingDir'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                dirPath = handleFileChooserResult(pakingDir, 'paking folder', getPathInfo(getDirectory(
                    title='Select Paking Folder',
                    initialDir=pakingDir if (pakingDir and os.path.isdir(pakingDir)) else os.getcwd(),
                ) or '')['best'])

                if not dirPath and False:
                    dirPath = DefaultPakingDir
                    sprintPad()
                    sprint(f'(using default)')
                    sprintSeparator()

                if pakingDir != dirPath:
                    pakingDir = dirPath
                    sprintPad()
                    sprint(f'Paking folder set to: {getPakingDirStr(shorten=False)}')
                else:
                    sprintPad()
                    sprint(f'Paking folder unchanged: {getPakingDirStr(shorten=False)}')
                if pakingDir != (menuSettings.get('pakingDir', None) or ''):
                    menuSettings['pakingDir'] = pakingDir
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('attachmentsDir'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                dirPath = handleFileChooserResult(attachmentsDir, 'attachments folder', getPathInfo(getDirectory(
                    title='Select Attachments Folder',
                    initialDir=attachmentsDir if (attachmentsDir and os.path.isdir(attachmentsDir)) else os.getcwd(),
                ) or '')['best'])

                if not dirPath and False:
                    dirPath = DefaultAttachmentsDir
                    sprintPad()
                    sprint(f'(using default)')
                    sprintSeparator()

                sprintPad()
                if attachmentsDir != dirPath:
                    attachmentsDir = dirPath
                    sprint(f'Attachments folder set to: {getAttachmentsDirStr(shorten=False)}')
                else:
                    sprint(f'Attachments folder unchanged: {getAttachmentsDirStr(shorten=False)}')
                if attachmentsDir != menuSettings.get('attachmentsDir', None):
                    menuSettings['attachmentsDir'] = attachmentsDir
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('unrealProjectDir'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                dirPath = handleFileChooserResult(unrealProjectDir, 'Unreal Engine project folder', getPathInfo(getDirectory(
                    title='Select Unreal Engine Project Folder',
                    mustExist=True,
                    initialDir=unrealProjectDir or os.getcwd(),
                ) or '')['best'])
                if unrealProjectDir != dirPath:
                    unrealProjectDir = dirPath
                    sprint(f'Unreal Engine project folder set to: {getUnrealProjectDirStr(shorten=False)}')
                else:
                    sprint(f'Unreal Engine project folder unchanged: {getUnrealProjectDirStr(shorten=False)}')
                if unrealProjectDir != menuSettings.get('unrealProjectDir', None):
                    menuSettings['unrealProjectDir'] = unrealProjectDir
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('uassetGuiPath'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                filePath = handleFileChooserResult(uassetGuiPath, UassetGuiProgramStem, getPathInfo(getFile(
                    title=f'Select {UassetGuiProgramStem} Program',
                    initialDir=os.path.dirname(uassetGuiPath) if uassetGuiPath else os.getcwd(),
                    initialFile=uassetGuiPath or None,
                    fileTypes=[('Programs', '.exe')],
                    mustExist=True,
                ) or '')['best'])
                if uassetGuiPath != filePath:
                    uassetGuiPath = filePath
                    sprint(f'{UassetGuiProgramStem} path set to: {getUassetGuiPathStr(shorten=False)}')
                else:
                    sprint(f'{UassetGuiProgramStem} path unchanged: {getUassetGuiPathStr(shorten=False)}')
                if uassetGuiPath != menuSettings.get('uassetGuiPath', None):
                    menuSettings['uassetGuiPath'] = uassetGuiPath
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('unrealPakPath'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                filePath = handleFileChooserResult(unrealPakPath, UnrealPakProgramStem, getPathInfo(getFile(
                    title=f'Select {UnrealPakProgramStem} Program',
                    initialDir=os.path.dirname(unrealPakPath) if unrealPakPath else os.getcwd(),
                    initialFile=unrealPakPath or None,
                    fileTypes=[('Programs', '.exe')],
                    mustExist=True,
                ) or '')['best'])
                if unrealPakPath != filePath:
                    unrealPakPath = filePath
                    sprint(f'{UnrealPakProgramStem} path set to: {getUnrealPakPathStr(shorten=False)}')
                else:
                    sprint(f'{UnrealPakProgramStem} path unchanged: {getUnrealPakPathStr(shorten=False)}')
                if unrealPakPath != menuSettings.get('unrealPakPath', None):
                    menuSettings['unrealPakPath'] = unrealPakPath
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('sigFile'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                filePath = handleFileChooserResult(sigFilePath, 'sig file', getPathInfo(getFile(
                    title=f'Select Sig File',
                    initialDir=os.path.dirname(sigFilePath) if sigFilePath else os.getcwd(),
                    initialFile=sigFilePath or None,
                    fileTypes=[('Sig', '.sig')],
                    mustExist=True,
                ) or '')['best'])
                if sigFilePath != filePath:
                    sigFilePath = filePath
                    sprint(f'sig file path set to: {getSigFilePathStr(shorten=False)}')
                else:
                    sprint(f'sig file path unchanged: {getSigFilePathStr(shorten=False)}')
                if sigFilePath != menuSettings.get('sigFilePath', None):
                    menuSettings['sigFilePath'] = sigFilePath
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('umodelPath'):
                prepActionRun()
                sprint('Opening file browser...')
                sprintPad()
                filePath = handleFileChooserResult(umodelPath, UnrealPakProgramStem, getPathInfo(getFile(
                    title=f'Select {UmodelProgramStem} Program',
                    initialDir=os.path.dirname(umodelPath) if umodelPath else os.getcwd(),
                    initialFile=umodelPath or None,
                    fileTypes=[('Programs', '.exe')],
                    mustExist=True,
                ) or '')['best'])
                if umodelPath != filePath:
                    umodelPath = filePath
                    sprint(f'{UmodelProgramStem} path set to: {getUmodelPathStr(shorten=False)}')
                else:
                    sprint(f'{UmodelProgramStem} path unchanged: {getUmodelPathStr(shorten=False)}')
                if umodelPath != menuSettings.get('umodelPath', None):
                    menuSettings['umodelPath'] = umodelPath
                    menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('modConfig'):
                prepActionRun()
                modConfigNames = (settings.get('modConfigs', {}).keys())
                sprint(f'Available mod configs ({len(modConfigNames)}): ')
                for modConfigNameIndex, modConfigName in enumerate(modConfigNames):
                    sprint(f'[ {modConfigNameIndex + 1} ] - {modConfigName}')
                if not modConfigNames:
                    sprintPad()
                    sprint('(no choices available - edit settings to populate `modConfigs`)')
                    sprintPad()
                else:
                    while True:
                        sprintPad()
                        inputStr = sprintput('Active mod config: ').strip()
                        sprintSeparator()
                        if not inputStr:
                            sprint(f'(canceled - active mod config unchanged)')
                            sprintPad()
                            break
                        else:
                            inputChoice = parseMenuItemFromToken(inputStr, modConfigNames)
                            if not inputChoice:
                                sprint('Invalid option.')
                                sprintSeparator()
                                continue
                            elif isinstance(inputChoice, list):
                                reportAmbigous(inputStr, inputChoice)
                                sprintSeparator()
                                continue
                            else:
                                userSpecifiedModConfigName = inputChoice
                                activeModConfigName = userSpecifiedModConfigName
                                sprint(f'Active mod config set to: "{activeModConfigName}"')
                                sprintPad()
                                break
                shouldPromptToContinue = True

            if popAction('list'):
                inspecting = True
                shouldRunMain = True
            if popAction('extract'):
                extractingAttachments = True
                shouldRunMain = True
            if popAction('create'):
                creatingAttachments = True
                shouldRunMain = True
            if popAction('rename'):
                renamingAttachmentFiles = True
                shouldRunMain = True
            if popAction('mix'):
                mixingAttachments = True
                shouldRunMain = True
            if popAction('upgrade'):
                upgradingMods = True
                shouldRunMain = True
            if popAction('pak'):
                paking = True
                shouldRunMain = True
            if popAction('install'):
                installingMods = True
                shouldRunMain = True
            if popAction('launch'):
                openingGameLauncher = True
                shouldRunMain = True
            if popAction('kill'):
                killingGame = True
                shouldRunMain = True
            if popAction('search'):
                searchingGameAssets = True
                shouldRunMain = True

            if popAction('edit'):
                prepActionRun()
                shouldPromptToContinue = shouldPromptToContinueForExternalApp
                sprintPad()
                sprint(f'Opening file "{settingsFilePath}"...')
                if not openFile(settingsFilePath):
                    sprintPad
                    esprint('ERROR: could not open file')
                    sprintPad()
                    shouldPromptToContinue = True
                sprintPad()

            if popAction('results'):
                prepActionRun()
                shouldPromptToContinue = shouldPromptToContinueForExternalApp
                filePath = getResultsFilePath(settingsFilePath)
                sprintPad()
                sprint(f'Opening file "{filePath}"')
                if not openFile(filePath):
                    sprintPad()
                    esprint('ERROR: could not open file')
                    sprintPad
                    shouldPromptToContinue = True
                sprintPad()

            popOpenPathAction('openSettingsDir', 'settings file', getPathInfo(settingsFilePath)['dir'], isDir=True)
            popOpenPathAction('openGameDir', 'game', gameDir, isDir=True)
            popOpenPathAction('openPakingDir', 'paking', pakingDir, isDir=True)
            popOpenPathAction('openAttachmentsDir', 'attachments', attachmentsDir, isDir=True)

            if popAction('debug'):
                prepActionRun()
                debug = not debug
                sprint(f"Turned debug flag {getOnOrOffStr(debug)}")
                sprintPad()
                menuSettings['debug'] = debug
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if popAction('dryRun'):
                prepActionRun()
                dryRun = not dryRun
                sprint(f"Turned dry run flag {getOnOrOffStr(dryRun)}")
                sprintPad()
                menuSettings['dryRun'] = dryRun
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if popAction('overwrite'):
                prepActionRun()
                if overwriteOverride:
                    overwriteOverride = False
                elif overwriteOverride is False:
                    overwriteOverride = None
                else:
                    overwriteOverride = True
                sprint(f"Switched overwrite mode to `{getOverwriteModeStr()}`")
                sprintPad()
                menuSettings['overwriteOverride'] = overwriteOverride
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if popAction('autoLaunch', 'auto'):
                prepActionRun()
                launcherStartsGame = not launcherStartsGame
                sprint(f"Turned auto launch flag {getOnOrOffStr(launcherStartsGame)}")
                sprintPad()
                menuSettings['launcherStartsGame'] = launcherStartsGame
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if shouldRunMain:
                prepActionRun()
                sprintPad()
                iterations = 1
                aggregateResultsFile = None
                resultsFilePath = getResultsFilePath(settingsFilePath)
                if True:
                    # TODO: refactor multiple iterations to be handled by ModSwapCommandRunner.runCommand()
                    if (
                        len(srcPakPaths) > 1
                        and not (settings.get('srcPakPaths', None) or '').strip()
                        and not creatingAttachments
                        and not renamingAttachmentFiles
                        and not openingGameLauncher
                        and not killingGame
                        and not searchingGameAssets
                    ):
                        iterations = len(srcPakPaths)
                        sprintPad()
                        sprint(f'Mulitiple pakchunks queued ({len(srcPakPaths)}):')
                        sprintPad()
                        for srcPakPath in srcPakPaths:
                            sprint(srcPakPath)
                        if not confirm(f'run action(s) on each packchunk (total runs: {len(srcPakPaths)})', emptyMeansNo=False, pad=True):
                            iterations = 0
                        else:
                            sprintSeparator()
                            aggregateResultsFile = tempfile.NamedTemporaryFile(
                                mode='w',
                                encoding='utf-8',
                                dir=getPathInfo(settingsFilePath)['dir'],
                                prefix=f'{getPathInfo(resultsFilePath)["stem"]}_',
                                suffix='.yaml',
                                delete=False,
                            )
                            aggregateResultsFile.write('results:\n')
                            aggregateResultsFile.flush()

                srcPakPathErrorCodeMap = {}
                for i in range(iterations):
                    srcPakPath = srcPakPaths[i] if i < len(srcPakPaths) else None

                    runner = ModSwapCommandRunner()
                    exitCode = runner.runCommand(
                        fromMenu=True,
                        settingsFilePath=settingsFilePath,
                        gameDir=gameDir,
                        gameVersion=gameVersion,
                        pakingDir=pakingDir,
                        attachmentsDir=attachmentsDir,
                        unrealProjectDir=unrealProjectDir,
                        uassetGuiPath=uassetGuiPath,
                        unrealPakPath=unrealPakPath,
                        sigFilePath=sigFilePath,
                        umodelPath=umodelPath,
                        activeModConfigName=activeModConfigName,
                        inspecting=inspecting,
                        creatingAttachments=creatingAttachments,
                        extractingAttachments=extractingAttachments,
                        renamingAttachmentFiles=renamingAttachmentFiles,
                        srcPakPath=srcPakPath,
                        customizationItemDbPath=customizationItemDbPath,
                        prevGameVersion=prevGameVersion,
                        upgradingMods=upgradingMods,
                        mixingAttachments=mixingAttachments,
                        paking=paking,
                        installingMods=installingMods,
                        openingGameLauncher=openingGameLauncher,
                        launcherStartsGame=launcherStartsGame,
                        killingGame=killingGame,
                        searchingGameAssets=searchingGameAssets,
                        nonInteractive=False,
                        debug=debug,
                        dryRun=dryRun,
                        overwriteOverride=overwriteOverride,
                    )
                    if exitCode:
                        srcPakPathErrorCodeMap[srcPakPath] = exitCode

                    if aggregateResultsFile is not None:
                        if runner.wroteResults:
                            with open(resultsFilePath, 'r', encoding='utf-8') as file:
                                isFirstLine = True
                                for line in file:
                                    if isFirstLine:
                                        aggregateResultsFile.write(f'- {srcPakPath}:\n')
                                        aggregateResultsFile.flush()
                                        isFirstLine = False

                                    aggregateResultsFile.write(f'  {line}')
                                    aggregateResultsFile.flush()

                if iterations > 1 and srcPakPathErrorCodeMap:
                    sprintSeparator()
                    esprint(f'Errors in {len(srcPakPathErrorCodeMap)} pakchunks:')
                    errorPakchunks = []
                    for srcPakPath, errorCode in srcPakPathErrorCodeMap.items():
                        sprint(f'{srcPakPath}: error code {errorCode}')
                        errorPakchunks.append(srcPakPath)
                    if errorPakchunks and aggregateResultsFile is not None:
                        yamlDump(
                            {
                                'errorPakchunks': errorPakchunks,
                            },
                            aggregateResultsFile,
                        )
                        aggregateResultsFile.flush()
                    sprintPad()

                if aggregateResultsFile is not None:
                    aggregateResultsFile.close()
                    sprint(f'{runner.dryRunPrefix}Moving aggregate results to "{resultsFilePath}"...')
                    shouldWrite = not runner.dryRun or (not runner.nonInteractive and confirm(f'write aggregate results "{resultsFilePath}" despite dry run', pad=True, emptyMeansNo=True))
                    written = False
                    if shouldWrite:
                        if runner.readyToWrite(resultsFilePath, dryRunHere=False):
                            shutil.move(aggregateResultsFile.name, resultsFilePath)
                            written = True
                    if written or runner.dryRun:
                        sprint(f'{runner.dryRunPrefix if not written else ""}Done moving.')
                    sprintPad()

                    if not written:
                        pathlib.Path(aggregateResultsFile).unlink(missing_ok=True)

                    aggregateResultsFile = None

                if openingGameLauncher and not dryRun:
                    # TODO: what if the exit code is bad? Then, set shouldPromptToContinue?
                    pass
                else:
                    shouldPromptToContinue = True

            if not shouldQuit:
                didPushMenu = False
                for actionName in actionNamesRemaining.copy():
                    subMenu = activeMenuSubMenuMap.get(actionName)
                    if subMenu is not None:
                        popAction(actionName)
                        pushMenu(subMenu)
                        didPushMenu = True
                        break

                if not didPushMenu and popAction('back'):
                    popMenu()

            if actionNamesRemaining:
                if ranPriorAction:
                    sprintSeparator()
                    if shouldPromptToContinue:
                        promptToContinue()
                sprintSeparator()
                esprint(f'Action(s) not run: {" | ".join(actionNamesRemaining)}')
                shouldPromptToContinue = True
                showingSeparator = True

        if shouldQuit:
            break

        if shouldPromptToContinue:
            sprintSeparator()
            promptToContinue()
            showingSeparator = True

        if showingSeparator:
            sprintSeparator()

    return exitCode
