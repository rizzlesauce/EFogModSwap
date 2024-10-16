import os

from customizationItemDbHelpers import CustomizationItemDbAssetName
from pakHelpers import UnrealPakProgramFilename, UnrealPakProgramStem
from pathHelpers import normPath
from programMetaData import ProgramName, Version
from uassetHelpers import UassetGuiProgramFilename, UassetGuiProgramStem
from unrealEngineHelpers import UassetFilenameSuffix

DefaultSettingsFileStem = 'settings'
DefaultSettingsPath = f'{DefaultSettingsFileStem}.yaml'
DefaultCustomizationItemDbPath = f'{CustomizationItemDbAssetName}{UassetFilenameSuffix}'
DefaultAttachmentsDir = 'attachments'
DefaultPakingDir = 'paking'

def getSettingsTemplate():
    return (
f'''# {ProgramName} {Version} settings.

# File paths can be relative or absolute.
# Pakchunk references can be abbreviated to `pakchunk<number>[name]`
# (pakchunk platform and file extension parts are optional)

## Inherited settings files

# Inherited settings files to load, in the order listed.
# If a particular setting (e.g., `modConfigs`) appears in more than one file,
# the setting from the latest listed file takes precendence,
# and settings in the current file here take ultimate precendence.
#import:
#- settings_common.yaml

## Tools paths

#unrealPakPath: C:/ModTools/{UnrealPakProgramStem}/{UnrealPakProgramFilename}
#uassetGuiPath: C:/ModTools/{UassetGuiProgramStem}/{UassetGuiProgramFilename}

## Staging and storage folders

# The folder used for storing, (un)paking, and editing pakchunks.
# This folder will be created if it doesn't already exist.
pakingDir: paking

# The folder used for storing socket attachment definition yaml files.
# This folder will be created if it doesn't already exist.
attachmentsDir: attachments

## Game paths

# Path to the game. Used for installing mods and launching the game.
#gameDir: C:/Dead By Daylight 4.4.2

# Top level folder within pakchunks and projects containing game files and cooked content.
gameName: DeadByDaylight

## Mod configurations

# Mods can be grouped and combined into different configurations so they
# can be easily swapped for different game play styles (e.g.,
# 1v1 vs 1v4). Configurations are lists of group names, while groups are
# simply named lists of pakchunks.

# Specify the active mod configuration
activeModConfig: legendary1v1
#activeModConfig: unmodded

# Mod configurations are combinations of mod groups. You can name a config whatever you want.
modConfigs:
  unmodded:
  - noMods
  1v4:
  - 1v4mods
  - baseMods
  1v1:
  - 1v1mods
  - baseMods
  legendary1v1:
  - legendaryMods
  - 1v1mods
  - baseMods

# Mod groups are named sets of related pakchunks. You can name the groups whatever you want.
modGroups:
  noMods: []
  1v1mods:
  - pakchunk790enhanced1v1-WindowsNoEditor
  1v4mods:
  - pakchunk781essential1v4-WindowsNoEditor
  - pakchunk782-WindowsNoEditor
  legendaryMods:
  - pakchunk827legendary-WindowsNoEditor
  - pakchunk828legend-WindowsNoEditor
  baseMods:
  - pakchunk584sweet-WindowsNoEditor
  - pakchunk631amazing-WindowsNoEditor
  - pakchunk742-WindowsNoEditor

# Reserved pakchunks are ones to ignore and never touch. For starters, these could be pakchunks
# that are part of the base game.
reservedPakchunks:
- pakchunk0-WindowsNoEditor
- pakchunk1-WindowsNoEditor
- pakchunk10-WindowsNoEditor
- pakchunk11-WindowsNoEditor
- pakchunk12-WindowsNoEditor
- pakchunk13-WindowsNoEditor
- pakchunk14-WindowsNoEditor
- pakchunk15-WindowsNoEditor
- pakchunk16-WindowsNoEditor
- pakchunk17-WindowsNoEditor
- pakchunk18-WindowsNoEditor
- pakchunk19-WindowsNoEditor
- pakchunk2-WindowsNoEditor
- pakchunk20-WindowsNoEditor
- pakchunk21-WindowsNoEditor
- pakchunk22-WindowsNoEditor
- pakchunk23-WindowsNoEditor
- pakchunk24-WindowsNoEditor
- pakchunk25-WindowsNoEditor
- pakchunk26-WindowsNoEditor
- pakchunk27-WindowsNoEditor
- pakchunk28-WindowsNoEditor
- pakchunk29-WindowsNoEditor
- pakchunk3-WindowsNoEditor
- pakchunk30-WindowsNoEditor
- pakchunk31-WindowsNoEditor
- pakchunk32-WindowsNoEditor
- pakchunk33-WindowsNoEditor
- pakchunk34-WindowsNoEditor
- pakchunk35-WindowsNoEditor
- pakchunk36-WindowsNoEditor
- pakchunk37-WindowsNoEditor
- pakchunk38-WindowsNoEditor
- pakchunk39-WindowsNoEditor
- pakchunk4-WindowsNoEditor
- pakchunk40-WindowsNoEditor
- pakchunk5-WindowsNoEditor
- pakchunk6-WindowsNoEditor
- pakchunk7-WindowsNoEditor
- pakchunk8-WindowsNoEditor
- pakchunk9-WindowsNoEditor

## Cooked asset paths

# Path to an Unreal Engine project if you want to use cooked assets from there.
#unrealProjectDir: C:/DeadByDaylightProject-master

# Path to a pakchunk pak or folder if you want to use cooked assets from there.
# This takes precedence over `unrealProjectDir`.
#srcPakPath: C:/ModTools/UnrealPak/pakchunk4321-WindowsNoEditor

# Path to {CustomizationItemDbAssetName} if mixing or manipulating custom slots.
# This can be either a UASSET file, or a JSON file saved from {UassetGuiProgramStem}.
# If the path begins with "/Content/", it will be treated like a relative game path
# within the pakchunk or unreal project specified above.
#customizationItemDbPath: /Content/Data/Dlc/<Mod name>/{CustomizationItemDbAssetName}
#customizationItemDbPath: {DefaultCustomizationItemDbPath}

## Target pakchunk specification

# Pakchunk name and number. If these are omitted and `srcPakPath` is specified,
# name and number will be extracted from the source pakchunk.
#destPakNumber: 4321
#destPakName: <ModName>
# This is uncommon
#destPakPlatformSuffix: 2

# Assets to include in the target pakchunk. If omitted or empty and `srcPakPath` is
# specified, it will be the list of assets in the source pakchunk.
#destPakAssets:
#- Data/Dlc/<Mod name>/{CustomizationItemDbAssetName}

## Attachment mixing preferences

# When mixing attachments into various model slots, the following settings are used to exclude duplicates
# and undesired combinations.

# These are attachments that are equivalent to the combination of other attachments.
# For example, KateLegsBlueChains is equivalent to combining KateLegsLeftBlueChain and KateLegsRightBlueChain.
# The mixer will make sure not to combine the equivalent attachment with its parts, and it will also skip combinations
# that include every part of the equivalent (to avoid duplicate slots).
equivalentParts:
  SurvivorLegs:
    # separated left/right sides of the original blue chains
    KateLegsBlueChains:
    - - KateLegsLeftBlueChain
      - KateLegsRightBlueChain
    # separated left/right sides of the shortened blue chains
    KateLegsShortBlueChains:
    - - KateLegsShortLeftBlueChain
      - KateLegsShortRightBlueChain

  SurvivorTorso:
    # separated backpack/necklace parts of the original backpack/necklace attachment
    KateBackpackAndBlueGemNecklace:
    - - KateBackpack
      - KateBlueGemNecklace

# Similar to, but slightly different than, equivalent parts, these parts are
# incompletely equivalent to a "proper superset" attachment
# (they make up part of the attachment precisely, but not all of it).
# An example of this is that Blue Chains is a proper superset of Short Blue Chains.
# These parts will never be combined with the superset attachment, avoiding duplicate slots.
supersetParts:
  SurvivorLegs:
    # define each shortened variant of blue chains as a proper subset of the corresponding original length version
    KateLegsBlueChains:
    - - KateLegsShortBlueChains
    KateLegsRightBlueChain:
    - - KateLegsShortRightBlueChain
    KateLegsLeftBlueChain:
    - - KateLegsShortLeftBlueChain

  # uncomment to use
  #SurvivorTorso:

# These are groups of mutually exclusive attachments (for example, backpacks).
mutuallyExclusive:
  # uncomment to use
  #SurvivorLegs:

  SurvivorTorso:
  # back conflict group 1
  - - KatePurpleHat
    - KateBackpack
    - MegHikingBackpack
    - MegSportBagWithShoes
    - NeaSkateboardBackpack

# Here we can define a list of attachments that conflict with a target attachment.
attachmentConflicts:
  # uncomment to use
  #SurvivorLegs:

  SurvivorTorso:
    KatePurpleHat:
    - KateBlueGemNecklace
    - KateGoldNecklaceNoRing
    - KateGuitar
    KateGuitar:
    - MegHikingBackpack
    - NeaSkateboardBackpack
    # optional - clipping is a bit noticeable
    - MegSportBagWithShoes
    # optional - clipping isn't too noticeable
    #- KateBackpack

# Skip attachment combinations that contain these combinations. By default, these apply to all base models
# in the target {CustomizationItemDbAssetName}. Syntax is available here ('==' and ':') to restrict exclusions. Using
# '==' after an attachment name means that it will skip the exact combination instead of
# all supersets of the combination. Additionally, ending the line with ':' and one or more comma separated base model
# names will limit the exclusion to those models only.
combosToSkip:
  SurvivorLegs:
  # remove long chains for the lower waistline pants in some legs variants
  - - KateLegsBlueChains:KateBikerVariantsRoughRider,KateBikerVariantsHellsAngel
  - - KateLegsLeftBlueChain:KateBikerVariantsRoughRider,KateBikerVariantsHellsAngel
  - - KateLegsRightBlueChain:KateBikerVariantsRoughRider,KateBikerVariantsHellsAngel
  # remove right side chain for legs variants with the walkie talkie
  - - KateLegsShortRightBlueChain:KateBikerVariantsGreenWalkieTalkie
  - - KateLegsShortRightBlueChain:KateBikerVariantsBlueWalkieTalkie

  SurvivorTorso:
  # items that conflict with purple hat
  - - KateBackpack
    - KatePurpleHat
  - - KateBlueGemNecklace
    - KatePurpleHat
  - - KateGoldNecklaceNoRing
    - KatePurpleHat
  - - KateGuitar
    - KatePurpleHat
  # skip the exact variants that already exist in another DLC or in the original game
  - - KateBikerJacketDanglingGloves==:KateBikerVariantsReadyToRide
  # (optional - can comment these out) remove double necklaces
  - - KateBlueGemNecklace
    - KateGoldNecklaceNoRing
'''
  )

def getContentDirRelativePath(path):
    path = normPath(path)
    start = '/Content/'
    if path.startswith(start):
        return path[len(start):]


def findSettingsFiles(dir='.'):
    for entry in os.scandir(dir):
        if (
            # TODO: remove
            (True or entry.name.lower().startswith(DefaultSettingsFileStem))
            and not entry.name.lower().startswith('.')
            and entry.name.lower().endswith('.yaml')
            and f'_{CustomizationItemDbAssetName}'.lower() not in entry.name.lower()
            and not entry.name.lower().endswith('-results.yaml')
            and not entry.name.lower().endswith('-altered.yaml')
            and not entry.name.lower().endswith('-unaltered.yaml')
        ):
            yield entry.name


def getResultsFilePath(settingsFilePath):
    return f"{settingsFilePath.removesuffix('.yaml')}-results.yaml"
