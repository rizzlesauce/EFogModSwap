import os
import platform

import yaml

from consoleHelpers import (esprint, promptToContinue, sprint, sprintPad,
                            sprintput, sprintSeparator)
from gameHelpers import getGameIsRunning, getGameServerIsRunning
from pathHelpers import getPathInfo
from programMetaData import ProgramName, Version
from runCommand import runCommand
from settingsHelpers import (DefaultSettingsPath, findSettingsFiles,
                             getResultsFilePath)
from uassetHelpers import UassetGuiProgramStem
from windowsHelpers import openFile, openFolder
from yamlHelpers import yamlDump


def reportAmbigous(commands, token):
    tokenLower = token.lower()

    def highlightedCommand(command):
        commandName = command['name']
        commandNameLower = commandName.lower()
        startIndex = commandNameLower.index(tokenLower)
        firstPart = commandName[:startIndex]
        lastPart = commandName[(startIndex + len(token)):]
        return f"{firstPart}{token.upper()}{lastPart}"

    esprint(f'"{token}" could be {" | ".join([highlightedCommand(c) for c in commands])}.')
    esprint('Type more of the word.')


def runMenu(args, parser):
    sprint(f'Welcome to {ProgramName}!')
    sprintPad()
    sprint('You can run one or more command targets by entering menu numbers or any part of the command name')

    exitCode = 0

    menuSettingsPath = '.menu_settings.yaml'
    menuSettings = {}
    if os.path.isfile(menuSettingsPath):
        try:
            with open(menuSettingsPath, 'r') as file:
                menuSettings = yaml.safe_load(file)
        except Exception as e:
            sprintPad()
            esprint(e)
            sprintPad()

    def saveMenuSettings():
        try:
            with open(menuSettingsPath, 'w') as file:
                yamlDump(menuSettings, file)
            return True
        except Exception as e:
            sprintPad()
            esprint(e)
            sprintPad()

    settingsFilePath = getPathInfo(args.settingsFilePath or menuSettings.get('settingsFilePath', DefaultSettingsPath))['best']
    uassetGuiPath = getPathInfo(args.uassetGuiPath or menuSettings.get('uassetGuiPath', ''))['best']
    debug = args.debug or menuSettings.get('debug', False)
    overwriteOverride = args.overwrite if args.overwrite is not None else menuSettings.get('overwriteOverride', None)

    actionsMap = {action.dest: action for action in parser._actions}

    availableCommandNames = [c for c in actionsMap.keys() if c not in {'ni', 'uassetGuiPath', 'unrealPakPath'}]
    availableCommandNames.insert(availableCommandNames.index('list') + 1, 'folder')
    availableCommandNames.insert(availableCommandNames.index('folder') + 1, 'editSettings')
    availableCommandNames.insert(availableCommandNames.index('editSettings') + 1, 'results')
    availableCommandNames.append('quit')
    commandMap = {c: { 'name': c, 'number': i + 1, 'action': actionsMap.get(c, None) } for i, c in enumerate(availableCommandNames)}
    commandNumberMap = {str(c['number']): c for c in commandMap.values()}

    def parseCommandFromToken(token):
        command = None

        tokenLower = token.lower()

        if not command:
            command = commandNumberMap.get(token, None)

        if not command:
            command = next((c for c in commandMap.values() if c['name'].lower() == tokenLower), None)

        if not command:
            commandMatches = [c for c in commandMap.values() if tokenLower in c['name'].lower()]
            if len(commandMatches) > 0:
                if len(commandMatches) == 1:
                    command = commandMatches[0]
                else:
                    command = commandMatches

        return command

    showingMenu = True
    menuSettingsDirty = False

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
            showServerRunning = False
            showGameRunning = False
            if showServerRunning:
                gameServerRunning = getGameServerIsRunning()
            if showGameRunning:
                gameRunning = getGameIsRunning()

            sprintPad()
            sprint(f"Settings file: {settingsFilePath or '<Not specified>'}")
            # TODO: remove
            if False:
                sprint(f"{UassetGuiProgramStem} path: {uassetGuiPath or '<Read from settings or use default>'}")
            sprint(f"Debug mode: {'on' if debug else 'off'}")
            sprint(f"Overwrite mode: {'overwrite' if overwriteOverride else 'no overwrite' if overwriteOverride is False else 'prompt'}")
            if showServerRunning:
                sprint(f'Game server running: {"yes" if gameServerRunning else "no"}')
            if showGameRunning:
                sprint(f'Game running: {"yes" if gameRunning else "no"}')

            sprintPad()

            for commandName in availableCommandNames:
                command = commandMap[commandName]
                if commandName == 'help':
                    help = 'show help page'
                elif commandName == 'version':
                    help = "show program version"
                elif commandName == 'settingsFilePath':
                    help = f"{'change' if settingsFilePath else 'set'} {command['action'].help}"
                elif commandName == 'uassetGuiPath':
                    help = f"{'change' if uassetGuiPath else 'set'} {command['action'].help}"
                elif commandName == 'quit':
                    help = "quit program"
                elif commandName == 'debug':
                    help = f"turn {'off' if debug else 'on'} debug flag ({'do not ' if debug else ''}{command['action'].help})"
                elif commandName == 'overwrite':
                    help = f"switch overwrite mode ({command['action'].help})"
                elif commandName == 'folder':
                    help = f'open settings folder in explorer'
                elif commandName == 'editSettings':
                    help = f'open settings in editor'
                elif commandName == 'results':
                    help = f'open command results in editor'
                elif command['action'] is not None:
                    help = command['action'].help
                else:
                    help = commandName

                sprint(f"[ {command['number']} ] {commandName[0].upper()}{commandName[1:]} - {help}")
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
        commands = []

        tokens = response.split()
        hasError = False
        results = [parseCommandFromToken(token) for token in tokens]

        # TODO: remove
        if False:
            sprintPad()
            sprintP(results)
            sprintPad()

        invalidTokens = []
        ambiguousMap = {}
        for token, result in zip(tokens, results):
            if isinstance(result, dict):
                commands.append(result)
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
                for token, commandNames in ambiguousMap.items():
                    sprintPad()
                    reportAmbigous(commandNames, token)
                    sprintPad()

            commands = []
            showingMenu = False

        if commands:
            shouldRunMain = False

            commandNamesRemaining = {c['name'] for c in commands}

            def popCommand(commandName):
                if commandName in commandNamesRemaining:
                    commandNamesRemaining.remove(commandName)
                    return commandName

            shouldPromptToContinueForSettings = False
            shouldPromptToContinueForExternalApp = False

            ranPriorCommand = False

            def prepCommandRun():
                nonlocal ranPriorCommand
                nonlocal shouldPromptToContinue
                nonlocal showingSeparator

                sprintSeparator()

                if ranPriorCommand:
                    if shouldPromptToContinue:
                        promptToContinue()
                        sprintSeparator()

                ranPriorCommand = True
                shouldPromptToContinue = False
                showingSeparator = True

            if popCommand('quit'):
                shouldQuit = True

            if popCommand('help'):
                prepCommandRun()
                sprint(parser.format_help())
                shouldPromptToContinue = True

            if popCommand('version'):
                prepCommandRun()
                sprint(f'Version: {parser.prog} {Version}')
                shouldPromptToContinue = True

            if popCommand('settingsFilePath'):
                prepCommandRun()
                filenames = []
                for filenameIndex, filename in enumerate(findSettingsFiles()):
                    if not len(filenames):
                        sprintPad()
                        sprint('Local settings files: ')
                    sprint(f'[ {filenameIndex + 1} ] - {filename}')
                    filenames.append(filename)
                while True:
                    sprintPad()
                    settingsFilePath = sprintput('Settings YAML file path (enter number of type a path): ').strip()
                    sprintPad()
                    if not settingsFilePath:
                        settingsFilePath = DefaultSettingsPath
                        sprintSeparator()
                        sprint(f'(using default)')
                        sprintPad()
                        break
                    else:
                        try:
                            fileNumber = int(settingsFilePath)
                        except:
                            fileNumber = None

                        if fileNumber is not None:
                            if fileNumber < 1 or fileNumber > len(filenames):
                                sprintPad()
                                esprint('Invalid option.')
                                sprintPad()
                            else:
                                settingsFilePath = filenames[fileNumber - 1]
                                break
                        else:
                            settingsFilePath = getPathInfo(settingsFilePath)['best']
                            break
                exists = os.path.isfile(settingsFilePath)
                sprintSeparator()
                sprint(f'Settings path set to: "{settingsFilePath}"{"" if exists else " (new file)"}')
                menuSettings['settingsFilePath'] = settingsFilePath
                menuSettingsDirty = True
                shouldPromptToContinue = True

            if popCommand('uassetGuiPath'):
                prepCommandRun()
                uassetGuiPath = sprintput(f'{UassetGuiProgramStem} path: ').strip()
                if not uassetGuiPath:
                    sprintPad()
                    sprint(f'(not specified)')
                else:
                    sprintPad()
                    sprint(f'{UassetGuiProgramStem} path set to: {uassetGuiPath}')
                menuSettings['uassetGuiPath'] = uassetGuiPath
                menuSettingsDirty = True
                shouldPromptToContinue = True

            if popCommand('list'):
                inspecting = True
                shouldRunMain = True
            if popCommand('extract'):
                extractingAttachments = True
                shouldRunMain = True
            if popCommand('create'):
                creatingAttachments = True
                shouldRunMain = True
            if popCommand('rename'):
                renaingAttachmentFiles = True
                shouldRunMain = True
            if popCommand('mix'):
                mixingAttachments = True
                shouldRunMain = True
            if popCommand('pak'):
                paking = True
                shouldRunMain = True
            if popCommand('install'):
                installingMods = True
                shouldRunMain = True
            if popCommand('launch'):
                openingGameLauncher = True
                shouldRunMain = True
            if popCommand('kill'):
                killingGame = True
                shouldRunMain = True

            if popCommand('editSettings'):
                prepCommandRun()
                shouldPromptToContinue = shouldPromptToContinueForExternalApp
                sprintPad()
                sprint(f'Opening file "{settingsFilePath}"...')
                if not openFile(settingsFilePath):
                    sprintPad
                    esprint('ERROR: could not open file')
                    sprintPad()
                    shouldPromptToContinue = True
                sprintPad()

            if popCommand('results'):
                prepCommandRun()
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

            if popCommand('folder'):
                prepCommandRun()
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

            if popCommand('debug'):
                prepCommandRun()
                debug = not debug
                sprint(f"Turned debug flag {'on' if debug else 'off'}")
                sprintPad()
                menuSettings['debug'] = debug
                menuSettingsDirty = True
                shouldPromptToContinue = shouldPromptToContinueForSettings

            if popCommand('overwrite'):
                prepCommandRun()
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
                prepCommandRun()
                sprintPad()
                exitCode = runCommand(
                    settingsFilePath=settingsFilePath,
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
                    uassetGuiPath=uassetGuiPath,
                    overwriteOverride=overwriteOverride,
                )
                if openingGameLauncher:
                    pass
                else:
                    shouldPromptToContinue = True

            if commandNamesRemaining:
                if ranPriorCommand:
                    sprintSeparator()
                    if shouldPromptToContinue:
                        promptToContinue()
                sprintSeparator()
                esprint(f'Command(s) not run: {" | ".join(commandNamesRemaining)}')
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
