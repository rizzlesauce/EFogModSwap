#!/usr/bin/env python3
"""
Module Docstring
"""

import argparse
import sys

from consoleHelpers import sprint, sprintPad
from customizationItemDbHelpers import CustomizationItemDbAssetName
from pathHelpers import getPathInfo
from programMetaData import ProgramName, Version
from runCommand import runCommand
from runMenu import runMenu
from settingsHelpers import DefaultSettingsPath
from uassetHelpers import UassetGuiProgramStem

__author__ = 'Ross Adamson'
__version__ = Version
__license__ = 'MIT'

if __name__ == '__main__':
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser(
        prog=ProgramName,
        description='''Swaps mods and character model accessories

Running with no arguments opens the interactive menu. To get started, select `List`
from the menu to create a settings file with helpful inline documentation. Then, choose
`Edit` from the menu to edit the settings file. In the settings file, set `gameDir` to
your game folder, and configure `modGroups` and `modConfigs` as desired. Finally,
run `ActiveModConfig`, `Install`, and `Launch` to start the game with your mod config.
'''.format(
            ProgramName=ProgramName,
            CustomizationItemDbResourceName=CustomizationItemDbAssetName,
            UassetGuiProgramStem=UassetGuiProgramStem,
        ),
    )
    parser.add_argument(
        'settingsFilePath',
        help=f'path to settings YAML file (defaults to `{getPathInfo(DefaultSettingsPath)["best"]}`)',
        type=str,
        nargs='?',
    )
    parser.add_argument(
        '--activeModConfig',
        help=f'set the active mod configuration (overrides `activeModConfig` setting)',
        type=str,
    )
    parser.add_argument(
        '--list',
        help='list, inspect, and collect data (and create a settings file if needed)',
        action='store_true',
    )
    parser.add_argument(
        '--extract',
        help='extract socket attachment definitions',
        action='store_true',
    )
    parser.add_argument(
        '--create',
        help='create socket attachment definitions interactively',
        action='store_true',
    )
    parser.add_argument(
        '--rename',
        help='rename attachment files to match their corresponding attachment ID (IDs should be globally unique)',
        action='store_true',
    )
    parser.add_argument(
        '--mix',
        help='mix socket attachments with character models',
        action='store_true',
    )
    parser.add_argument(
        '--pak',
        help='pak content into pakchunk',
        action='store_true',
    )
    parser.add_argument(
        '--install',
        help='intall active mod configuration into the game',
        action='store_true',
    )
    parser.add_argument(
        '--launch',
        help='open game launcher menu and start the game',
        action='store_true',
    )
    parser.add_argument(
        '--kill',
        help='kill running game',
        action='store_true',
    )
    parser.add_argument(
        '--overwrite',
        help='force or prevent file overwrites without prompting',
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        '--dry',
        help='run without making changes to mods to see what would happen',
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        '--debug',
        help='output extra debug info to the console',
        action='store_true',
    )
    parser.add_argument(
        '-ni',
        help='run in non-interactive mode',
        action='store_true',
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {Version}',
    )
    args = parser.parse_args()

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
        and not args.ni
    ):
        exitCode = runMenu(args, parser)
    else:
        exitCode = runCommand(
            settingsFilePath=args.settingsFilePath,
            activeModConfigName=args.activeModConfig,
            inspecting=args.list,
            creatingAttachments=args.create,
            extractingAttachments=args.extract,
            renamingAttachmentFiles=args.rename,
            mixingAttachments=args.mix,
            paking=args.pak,
            installingMods=args.install,
            openingGameLauncher=args.launch,
            killingGame=args.kill,
            uassetGuiPath=args.uassetGuiPath,
            dryRun=args.dry,
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
