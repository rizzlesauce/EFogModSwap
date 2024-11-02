#!/usr/bin/env python3
"""
Module Docstring
"""

import argparse
import sys

from dbdmodswap.helpers.consoleHelpers import (setConsoleWindow, sprint,
                                               sprintPad)
from dbdmodswap.helpers.customizationItemDbHelpers import \
    CustomizationItemDbAssetName
from dbdmodswap.helpers.guiHelpers import getForegroundWindow
from dbdmodswap.helpers.pakHelpers import UnrealPakProgramFilename
from dbdmodswap.helpers.pathHelpers import getPathInfo
from dbdmodswap.helpers.settingsHelpers import (DefaultAttachmentsDir,
                                                DefaultGameVersion,
                                                DefaultPakingDir,
                                                DefaultSettingsPath,
                                                getEnabledDisabledStr)
from dbdmodswap.helpers.uassetHelpers import (UassetGuiProgramFilename,
                                              UassetGuiProgramStem)
from dbdmodswap.helpers.umodelHelpers import UmodelProgramFilename
from dbdmodswap.helpers.windowsHelpers import setConsoleTitle
from dbdmodswap.metadata.programMetaData import (Author, ConsoleTitle, License,
                                                 ProgramName, Version)
from dbdmodswap.runtime.runCommand import (DbdModSwapCommandRunner,
                                           DefaultLauncherStartsGame)
from dbdmodswap.runtime.runMenu import runMenu

__author__ = Author
__version__ = Version
__license__ = License

if __name__ == '__main__':
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser(
        prog=ProgramName,
        description='''Swaps mod configs and character model accessories

Running with no arguments opens the interactive menu. To get started, configure the
game folder by selecting `MoreOptions`, `GameDir` and choosing the game folder from
the file browser that opens. Then, set the `GameVersion` from the same menu.
Select `List` from the main menu to create a settings
file with helpful inline documentation. Select `Edit` from the menu to edit the
settings file, configuring `modGroups` and `modConfigs`. Finally, run `ActiveModConfig`,
`Install`, and `Launch` to start the game with your selected mod configuration.
'''.format(
            ProgramName=ProgramName,
            CustomizationItemDbResourceName=CustomizationItemDbAssetName,
            UassetGuiProgramStem=UassetGuiProgramStem,
        ),
    )
    parser.add_argument(
        'settingsFile',
        help=f'path to settings YAML file (default: `{getPathInfo(DefaultSettingsPath)["best"]}`)',
        type=str,
        nargs='?',
    )
    parser.add_argument(
        '--gameDir',
        help='game folder',
        type=str,
    )
    parser.add_argument(
        '--gameVersion',
        help=f'game version (default: `{DefaultGameVersion}`)',
        type=str,
    )
    parser.add_argument(
        '--pakingDir',
        help=f'pakchunks storage folder (default: `{getPathInfo(DefaultPakingDir)["best"]}-<gameVersion>`)',
        type=str,
    )
    parser.add_argument(
        '--attachmentsDir',
        help=f'attachment definitions storage folder (default: `{getPathInfo(DefaultAttachmentsDir)["best"]}-<gameVersion>`)',
        type=str,
    )
    parser.add_argument(
        '--unrealProjectDir',
        help='Unreal Engine project folder',
        type=str,
    )
    parser.add_argument(
        '--uassetGuiPath',
        help=f'path to {UassetGuiProgramFilename}',
        type=str,
    )
    parser.add_argument(
        '--unrealPakPath',
        help=f'path to {UnrealPakProgramFilename}',
        type=str,
    )
    parser.add_argument(
        '--sigFile',
        help=f'path to sig file',
        type=str,
    )
    parser.add_argument(
        '--umodelPath',
        help=f'path to {UmodelProgramFilename}',
        type=str,
    )
    parser.add_argument(
        '--activeModConfig',
        help=f'override active mod configuration',
        type=str,
    )
    parser.add_argument(
        '--list',
        help='list, inspect, and collect data (and create a settings file if needed)',
        action='store_true',
    )
    parser.add_argument(
        '--create',
        help='create socket attachments interactively',
        action='store_true',
    )
    parser.add_argument(
        '--extract',
        help='extract socket attachment definitions',
        action='store_true',
    )
    parser.add_argument(
        '--rename',
        help='rename each attachment file to match its attachment name',
        action='store_true',
    )
    parser.add_argument(
        '--mix',
        help='mix socket attachments with character models',
        action='store_true',
    )
    parser.add_argument(
        '--pak',
        help='pak content into a pakchunk',
        action='store_true',
    )
    parser.add_argument(
        '--install',
        help='apply the active mod config to the game',
        action='store_true',
    )
    parser.add_argument(
        '--launch',
        help='enter game launcher menu (and optionally auto launch the game)',
        action='store_true',
    )
    parser.add_argument(
        '--autoLaunch',
        help=f'automatically start the game when entering the launcher menu (default: {getEnabledDisabledStr(DefaultLauncherStartsGame)})',
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        '--kill',
        help='end game processes if they are running',
        action='store_true',
    )
    parser.add_argument(
        '--search',
        help='search pakchunks and assets',
        action='store_true',
    )
    parser.add_argument(
        '--overwrite',
        help='overwrite existing files (default: ask to confirm)',
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        '--dryRun',
        help='simulate actions without making any changes (may still write temporary files)',
        action='store_true',
    )
    parser.add_argument(
        '--debug',
        help='output extra info to the console',
        action='store_true',
    )
    parser.add_argument(
        '-ni',
        help='run non-interactively',
        action='store_true',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {Version}',
    )
    args = parser.parse_args()

    setConsoleWindow(getForegroundWindow())
    setConsoleTitle(ConsoleTitle)

    if args.ni:
        sprint('Running in non-interactive mode.')

    if (
        not args.list
        and not args.extract
        and not args.create
        and not args.rename
        and not args.mix
        and not args.pak
        and not args.install
        and not args.launch
        and not args.kill
        and not args.search
        and not args.ni
    ):
        exitCode = runMenu(args, parser)
    else:
        runner = DbdModSwapCommandRunner()
        exitCode = runner.runCommand(
            settingsFilePath=args.settingsFile,
            gameDir=args.gameDir,
            gameVersion=args.gameVersion,
            pakingDir=args.pakingDir,
            attachmentsDir=args.attachmentsDir,
            unrealProjectDir=args.unrealProjectDir,
            activeModConfigName=args.activeModConfig,
            inspecting=args.list,
            creatingAttachments=args.create,
            extractingAttachments=args.extract,
            renamingAttachmentFiles=args.rename,
            mixingAttachments=args.mix,
            paking=args.pak,
            installingMods=args.install,
            openingGameLauncher=args.launch,
            launcherStartsGame=args.autoLaunch,
            killingGame=args.kill,
            searchingGameAssets=args.search,
            uassetGuiPath=args.uassetGuiPath,
            unrealPakPath=args.unrealPakPath,
            sigFilePath=args.sigFile,
            umodelPath=args.umodelPath,
            dryRun=args.dryRun,
            overwriteOverride=args.overwrite,
            debug=args.debug,
            nonInteractive=args.ni,
        )

    # TODO: remove
    if False:
        if not len(sys.argv) > 1:
            sprintPad()
            sprint(f'run `{parser.prog} -h` for more options and usage.')
            sprintPad()

    sys.exit(exitCode)
