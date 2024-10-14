#!/usr/bin/env python3
"""
Module Docstring
"""

import argparse
import sys

from customizationItemDbHelpers import CustomizationItemDbAssetName
from pakHelpers import UnrealPakProgramFilename
from pathHelpers import getPathInfo
from consoleHelpers import sprint, sprintPad
from programMetaData import ProgramName, Version
from runCommand import runCommand
from runMenu import runMenu
from settingsHelpers import (DefaultSettingsPath, DefaultUassetGuiPath,
                             DefaultUnrealPakPath)
from uassetHelpers import UassetGuiProgramFilename, UassetGuiProgramStem

__author__ = 'Ross Adamson'
__version__ = Version
__license__ = 'MIT'

if __name__ == '__main__':
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser(
        prog=ProgramName,
        description='''Mixes socket attachments with character models.

Can also extract socket attachment definitions from a {CustomizationItemDbResourceName}.
A YAML settings file specifies the input {CustomizationItemDbResourceName} file and the
mix options.

{UassetGuiProgramStem} can be used to export a {CustomizationItemDbResourceName}.uasset file to JSON.
{ProgramName} reads that JSON file and writes an altered version that
can be converted back to the original uasset file using {UassetGuiProgramStem}.
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
        '--uassetGuiPath',
        help=f'path to {UassetGuiProgramFilename} (defaults to `{getPathInfo(DefaultUassetGuiPath)["best"]}`)',
        type=str,
    )
    parser.add_argument(
        '--unrealPakPath',
        help=f'path to {UnrealPakProgramFilename} (defaults to `{getPathInfo(DefaultUnrealPakPath)["best"]}`)',
        type=str,
    )
    parser.add_argument(
        '--list',
        help='list, inspect, and collect data',
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
        help='open game launcher',
        action='store_true',
    )
    parser.add_argument(
        '--kill',
        help='kill running game',
        action='store_true',
    )
    parser.add_argument(
        '-ni',
        help='run in non-interactive mode',
        action='store_true',
    )
    parser.add_argument(
        '--debug',
        help='output extra debug info to the console',
        action='store_true',
    )
    parser.add_argument(
        '--overwrite',
        help='force or prevent file overwrites without prompting',
        action=argparse.BooleanOptionalAction,
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
            inspecting=args.list,
            creatingAttachments=args.create,
            extractingAttachments=args.extract,
            renamingAttachmentFiles=args.rename,
            mixingAttachments=args.mix,
            paking=args.pak,
            installingMods=args.install,
            openingGameLauncher=args.launch,
            killingGame=args.kill,
            nonInteractive=args.ni,
            debug=args.debug,
            uassetGuiPath=args.uassetGuiPath,
            overwriteOverride=args.overwrite,
        )

    # TODO: remove
    if False:
        if not len(sys.argv) > 1:
            sprintPad()
            sprint(f'run `{parser.prog} -h` for more options and usage.')
            sprintPad()

    sys.exit(exitCode)
