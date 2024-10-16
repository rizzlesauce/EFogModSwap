import os
import platform

import yaml

from consoleHelpers import (esprint, promptToContinue, sprint, sprintClear,
                            sprintPad, sprintput, sprintSeparator)
from gameHelpers import getGameIsRunning, getGameServerIsRunning
from pathHelpers import getPathInfo
from programMetaData import ProgramName, Version
from runCommand import readSettingsRecursive, runCommand
from settingsHelpers import (DefaultSettingsPath, findSettingsFiles,
                             getResultsFilePath)
from windowsHelpers import openFile, openFolder
from yamlHelpers import yamlDump


def reportAmbigous(token, matchingItems):
    tokenLower = token.lower()

    def highlightedMenuItem(item):
        itemName = item if isinstance(item, str) else item['name']
        itemNameLower = itemName.lower()
        startIndex = itemNameLower.index(tokenLower)
        firstPart = itemName[:startIndex]
        lastPart = itemName[(startIndex + len(token)):]
        return f"{firstPart}{token.upper()}{lastPart}"

    esprint(f'"{token}" could be {" | ".join([highlightedMenuItem(item) for item in matchingItems])}.')
    esprint('Type more of the word.')


def parseMenuItemFromToken(token, menuItems, allowExact=True, allowSubset=True, allowCustom=False):
    token = (token or '').strip()
    tokenLower = token.lower()

    result = None

    if tokenLower:
        menuNumberItemMap = {i + 1: item for i, item in enumerate(menuItems)}
        menuItemNamesLower = [(item if isinstance(item, str) else item['name']).lower() for item in menuItems]
        menuNameItemMap = {name: item for name, item in zip(menuItemNamesLower, menuItems)}

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
                result = menuNameItemMap.get(tokenLower, None)

            if not result and allowSubset:
                resultMatches = [item for name, item in menuNameItemMap.items() if tokenLower in name]
                if len(resultMatches) == 1:
                    result = resultMatches[0]
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
            with open(menuSettingsPath, 'w') as file:
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
                    with open(menuSettingsPath, 'r') as file:
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
        else:
            break

    sprintPad()
    sprint('You can run one or multiple actions by entering menu numbers or parts of menu item names.')

    exitCode = 0

    settingsFilePath = getPathInfo(args.settingsFilePath or menuSettings.get('settingsFilePath', DefaultSettingsPath))['best']
    settingsFileExists = False
    settingsFileValid = False
    settings = {}
    userSpecifiedModConfigName = (args.activeModConfig or '').strip() or menuSettings.get('activeModConfig', None)
    activeModConfigName = None
    activeModConfigExists = False
    debug = args.debug or menuSettings.get('debug', False)
    dryRun = args.dry or menuSettings.get('dryRun', False)
    overwriteOverride = args.overwrite if args.overwrite is not None else menuSettings.get('overwriteOverride', None)

    def getSettingsFileStr():
        return f'"{settingsFilePath}"{(" (loaded)" if settingsFileValid else " (invalid)") if settingsFileExists else " (new file)"}' if settingsFilePath else '<Not specified>'

    def getActiveModConfigStr():
        # TODO: report whether mod config is verified to be installed or not, and whether it matches `activeModConfig` settings
        return f'"{activeModConfigName}"{("" if activeModConfigExists else " (missing)")}' if activeModConfigName else '<Not specified>'

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

    mainMenuItems = [
        {'title': 'Game'},
        'activeModConfig',
        'install',
        'launch',
        'kill',
        {'title': 'Settings'},
        'settingsFilePath',
        'edit',
        'results',
        'folder',
        {'title': 'Modding'},
        'list',
        'extract',
        'create',
        'rename',
        'mix',
        'pak',
        {'title': 'Flags'},
        'overwrite',
        'dry',
        'debug',
        {'title': 'About'},
        'version',
        'help',
        'quit',
    ]
    mainMenuActionNames = [item for item in mainMenuItems if isinstance(item, str)]
    mainMenuActionNameMap = {actionName: { 'name': actionName, 'number': i + 1, 'action': actionsMap.get(actionName, None) } for i, actionName in enumerate(mainMenuActionNames)}
    mainMenuActions = mainMenuActionNameMap.values()

    while True:
        inspecting = False
        creatingAttachments = False
        extractingAttachments = False
        renaingAttachmentFiles = False
        mixingAttachments = False
        paking = False
        installingMods = False
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
                gameRunning = getGameIsRunning()

            sprintPad()
            sprint(f'Settings file: {getSettingsFileStr()}')
            sprint(f'Active mod config: {getActiveModConfigStr()}')
            sprint(f"Overwrite mode: {'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}")
            sprint(f"Dry run: {'yes' if dryRun else 'no'}")
            sprint(f"Debug: {'yes' if debug else 'no'}")
            if showServerRunning:
                sprint(f'Game server running: {"yes" if gameServerRunning else "no"}')
            if showGameRunning:
                sprint(f'Game running: {"yes" if gameRunning else "no"}')

            sprintPad()

            for menuItem in mainMenuItems:
                if not isinstance(menuItem, str):
                    title = menuItem.get('title', '')
                    if title:
                        sprint(f'------------  {title}  ------------')
                    else:
                        sprintPad()
                    continue

                actionName = menuItem
                action = mainMenuActionNameMap[actionName]
                if actionName == 'help':
                    help = 'show help page'
                elif actionName == 'version':
                    help = "show program version"
                elif actionName == 'settingsFilePath':
                    help = 'select the current configuration file'
                elif actionName == 'quit':
                    help = "quit program"
                elif actionName == 'debug':
                    help = f"turn {'off' if debug else 'on'} debug flag ({'do not ' if debug else ''}{action['action'].help})"
                elif actionName == 'dry':
                    help = f"turn {'off' if dryRun else 'on'} dry flag ({'do not ' if dryRun else ''}{action['action'].help})"
                elif actionName == 'overwrite':
                    help = f"switch overwrite mode ({action['action'].help})"
                elif actionName == 'folder':
                    help = f'open settings folder in explorer'
                elif actionName == 'edit':
                    help = f'open settings in editor'
                elif actionName == 'results':
                    help = f'open action results in editor'
                elif action['action'] is not None:
                    help = action['action'].help
                else:
                    help = actionName

                sprint(f"[ {action['number']} ] {actionName[0].upper()}{actionName[1:]} - {help}")
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
        results = [parseMenuItemFromToken(token, mainMenuActions) for token in tokens]

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
                for token, actionNames in ambiguousMap.items():
                    sprintPad()
                    reportAmbigous(token, actionNames)
                    sprintPad()

            actions = []
            showingMenu = False

        if actions:
            shouldRunMain = False

            actionNamesRemaining = {action['name'] for action in actions}

            def popAction(actionName):
                if actionName in actionNamesRemaining:
                    actionNamesRemaining.remove(actionName)
                    return actionName

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
                shouldPromptToContinue = True

            if popAction('settingsFilePath'):
                prepActionRun()
                filenames = []
                for filenameIndex, filename in enumerate(findSettingsFiles()):
                    if not len(filenames):
                        sprintPad()
                        sprint('Local settings files: ')
                    sprint(f'[ {filenameIndex + 1} ] - {filename}')
                    filenames.append(filename)
                while True:
                    sprintPad()
                    inputStr = sprintput('Settings YAML file path (enter number of type a path): ').strip()
                    sprintPad()
                    if not inputStr:
                        settingsFilePath = DefaultSettingsPath
                        sprintSeparator()
                        sprint(f'(using default)')
                        sprintPad()
                        break
                    else:
                        allowSubset = (
                            inputStr[0] not in {'.', '/', '\\'}
                            and not inputStr.lower().endswith('.yaml')
                        )
                        inputChoice = parseMenuItemFromToken(inputStr, filenames, allowExact=True, allowSubset=allowSubset, allowCustom=True)
                        if not inputChoice:
                            sprintPad()
                            esprint('Invalid option.')
                            sprintPad()
                        elif isinstance(inputChoice, list):
                            reportAmbigous(inputStr, inputChoice)
                        elif not inputChoice.lower().endswith('.yaml'):
                            sprintPad()
                            esprint('Invalid path (missing ".yaml" file extension)')
                            sprintPad()
                        else:
                            settingsFilePath = getPathInfo(inputChoice)['best']
                            break
                readSettings()
                sprintSeparator()
                sprint(f'Settings path set to: {getSettingsFileStr()}')
                menuSettings['settingsFilePath'] = settingsFilePath
                menuSettingsDirty = True
                shouldPromptToContinue = True

            if popAction('activeModConfig'):
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
                        sprintPad()
                        if not inputStr:
                            sprintSeparator()
                            sprint(f'(canceled - active mod config unchanged)')
                            sprintPad()
                            break
                        else:
                            inputChoice = parseMenuItemFromToken(inputStr, modConfigNames)
                            if not inputChoice:
                                sprintPad()
                                sprint('Invalid option.')
                                sprintPad()
                            elif isinstance(inputChoice, list):
                                reportAmbigous(token, inputChoice)
                            else:
                                userSpecifiedModConfigName = inputChoice
                                activeModConfigName = userSpecifiedModConfigName
                                sprintPad()
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
                renaingAttachmentFiles = True
                shouldRunMain = True
            if popAction('mix'):
                mixingAttachments = True
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

            if popAction('folder'):
                prepActionRun()
                shouldPromptToContinue = shouldPromptToContinueForExternalApp
                if platform.system() != 'Windows':
                    sprintPad()
                    esprint('Only supported on Windows')
                    shouldPromptToContinue = True
                else:
                    settingsPathInfo = getPathInfo(settingsFilePath)
                    settingsDir = settingsPathInfo['dir']
                    sprintPad()
                    sprint(f'Opening {settingsDir}')
                    try:
                        openFolder(settingsDir)
                    except Exception as e:
                        sprintPad()
                        esprint(e)
                        sprintPad()
                        shouldPromptToContinue = True
                sprintPad()

            if popAction('debug'):
                prepActionRun()
                debug = not debug
                sprint(f"Turned debug flag {'on' if debug else 'off'}")
                sprintPad()
                menuSettings['debug'] = debug
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if popAction('dry'):
                prepActionRun()
                dryRun = not dryRun
                sprint(f"Turned dryRun flag {'on' if dryRun else 'off'}")
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
                sprint(f"Switched overwrite mode to `{'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}`")
                sprintPad()
                menuSettings['overwriteOverride'] = overwriteOverride
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if shouldRunMain:
                prepActionRun()
                sprintPad()
                exitCode = runCommand(
                    settingsFilePath=settingsFilePath,
                    activeModConfigName=activeModConfigName,
                    inspecting=inspecting,
                    creatingAttachments=creatingAttachments,
                    extractingAttachments=extractingAttachments,
                    renamingAttachmentFiles=renaingAttachmentFiles,
                    mixingAttachments=mixingAttachments,
                    paking=paking,
                    installingMods=installingMods,
                    openingGameLauncher=openingGameLauncher,
                    killingGame=killingGame,
                    nonInteractive=False,
                    debug=debug,
                    dryRun=dryRun,
                    overwriteOverride=overwriteOverride,
                )
                if openingGameLauncher and not dryRun:
                    # TODO: what if the exit code is bad? Then, set shouldPromptToContinue?
                    pass
                else:
                    shouldPromptToContinue = True

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
