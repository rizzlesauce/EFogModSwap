import os

from modswap.helpers.gameHelpers import (DefaultGameVersion,
                                         DefaultPrevGameVersion)
from modswap.metadata.programMetaData import ProgramName, Version

from .customizationItemDbHelpers import CustomizationItemDbAssetName
from .gameHelpers import (DefaultGameName, getDefaultGameProgramName,
                          getGameUnrealEngineVersion)
from .pakHelpers import UnrealPakProgramFilename, UnrealPakProgramStem
from .pathHelpers import normPath
from .uassetHelpers import UassetGuiProgramFilename, UassetGuiProgramStem
from .umodelHelpers import UmodelProgramFilename, UmodelProgramStem
from .unrealEngineHelpers import UassetFilenameSuffix

DefaultSettingsFileStem = 'settings'
DefaultSettingsPath = f'{DefaultSettingsFileStem}.yaml'
DefaultCustomizationItemDbPath = f'{CustomizationItemDbAssetName}{UassetFilenameSuffix}'
DefaultAttachmentsDir = 'attachments'
DefaultPakingDir = 'paking'

def getGameName(settings):
    gameName = (settings.get('gameName', None) or '').strip() or DefaultGameName
    return gameName


def getGameProgramName(settings):
    gameProgramName = settings.get('gameProgramName', None)
    if gameProgramName:
      return gameProgramName

    gameName = getGameName(settings)
    if gameName:
      return getDefaultGameProgramName(gameName)


def getGameVersion(settings):
    return settings.get('gameVersion', None) or DefaultGameVersion


def getPrevGameVersion(settings):
    return settings.get('prevGameVersion', None) or DefaultPrevGameVersion


def getUnrealEngineVersion(settings):
    version = settings.get('unrealEngineVersion', None)
    if version:
        return version

    gameVersion = getGameVersion(settings)
    if gameVersion:
        return getGameUnrealEngineVersion(gameVersion)


def getSettingsTemplate(**kwargs):
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

{
    f'unrealPakPath: {kwargs["unrealPakPath"]}' if kwargs.get('unrealPakPath', None)
    else f'#unrealPakPath: C:/ModTools/{UnrealPakProgramStem}/{UnrealPakProgramFilename}'
}
{
    f'uassetGuiPath: {kwargs["uassetGuiPath"]}' if kwargs.get('uassetGuiPath', None)
    else f'#uassetGuiPath: C:/ModTools/{UassetGuiProgramStem}/{UassetGuiProgramFilename}'
}
{
    f'umodelPath: {kwargs["umodelPath"]}' if kwargs.get('umodelPath', None)
    else f'#umodelPath: C:/ModTools/{UmodelProgramStem}/{UmodelProgramFilename}'
}

# If your game requires a sig file for each pakchunk, set the path to the sig file here
{
    f'sigFilePath: {kwargs["sigFilePath"]}' if kwargs.get('sigFilePath', None)
    else f'#sigFilePath: C:/ModTools/{UnrealPakProgramStem}/Resources/copy.sig'
}

# If omitted, {ProgramName} will detect this based on the `gameVersion` (if it recognizes the game version)
#unrealEngineVersion: '{getUnrealEngineVersion(kwargs) or "''"}'

## Staging and storage folders

# The folder used for storing, (un)paking, and editing pakchunks.
# This folder will be created if it doesn't already exist.
{
    f'pakingDir: {kwargs["pakingDir"]}' if kwargs.get('pakingDir', None)
    else f"pakingDir: {DefaultPakingDir}-{getGameVersion(kwargs) or 'unknownGameVersion'}"
}

# The folder used for storing socket attachment definition yaml files.
# This folder will be created if it doesn't already exist.
{
    f'attachmentsDir: {kwargs["attachmentsDir"]}' if kwargs.get('attachmentsDir', None)
    else f"attachmentsDir: {DefaultAttachmentsDir}-{getGameVersion(kwargs) or 'unknownGameVersion'}"
}

## Game paths

# Path to the game. Used for installing mods and launching the game.
{
    f'gameDir: {kwargs["gameDir"]}' if kwargs.get('gameDir', None)
    else '#gameDir: C:/EFog-6.5.1'
}

# Top level folder within pakchunks and projects containing game files and cooked content.
gameName: {getGameName(kwargs) or "''"}

# Game program name
gameProgramName: {getGameProgramName(kwargs) or "''"}

# Game version
gameVersion: '{getGameVersion(kwargs) or "''"}'

# Previous game version (if upgrading mods)
prevGameVersion: '{getPrevGameVersion(kwargs) or "''"}'

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
{
    f'unrealProjectDir: {kwargs["unrealProjectDir"]}' if kwargs.get('unrealProjectDir', None)
    else f'#unrealProjectDir: C:/Modding/UEProjects/{DefaultGameName}'
}

# Path to a pakchunk pak or folder if you want to use cooked assets from there.
# This takes precedence over `unrealProjectDir`.
#srcPakPath: C:/ModTools/UnrealPak/pakchunk4321-WindowsNoEditor

# Path to cooked assets outside of a pakchunk or unreal project. {ProgramName} will generate
# new asset files here when copying attachment blueprints to make new attachments.
{
    f'extraContentDir: {kwargs["extraContentDir"]}' if kwargs.get('extraContentDir', None)
    else f"extraContentDir: assets-{getGameVersion(kwargs) or 'unknownGameVersion'}"
}

# Path to {CustomizationItemDbAssetName} if mixing or manipulating custom cosmetic slots.
# This can be either a UASSET file, or a JSON file saved from {UassetGuiProgramStem}.
# If the path begins with "/Content/", it will be treated like a relative game path
# within the pakchunk or unreal project specified above. This can also be a wildcard
# (/Content/**/CustomizationItemDB).
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
# names will limit the exclusion to those models only. If you use '==' without an attachment name, it will exclude
# the base model (the model with no attachments) from the resulting cosmetic slots.
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
  # exclude base model (it's already included in the game; or, the base model needs a certain attachment to look right)
  - - ==:KateDefault
  # this base model is incomplete without the KateBouncingBellyTorso attachment, so exclude it on its own
  - - ==:KatePregnant
  # (optional - can comment these out) remove double necklaces
  - - KateBlueGemNecklace
    - KateGoldNecklaceNoRing

# Require some attachment combinations - if a combination doesn't include these combinations, exclude it.
# This can be helpful for making sure an essential attachment for a model is present in every custom cosmetic slot.
combosRequired:
  SurvivorTorso:
  # this base mode is incomplete without this attachment, so always include it
  - - KateBouncingBellyTorso:KatePregnant

## Game asset searching parameters

# These are all optional properties and you can comment out any that you don't need.

# Asset path search terms
#searchAssetNameMatchers:
## looking for blueprints
#- blu
#- ab_
#- bp_

# Look for assets that include these search terms in their name map entries
#searchNameMapNameMatchers:
#- AnimBlueprintGeneratedClass
#- PerBoneBlendWeight

# Look for assets that include these search terms in their json string converted with {UassetGuiProgramStem}
#searchJsonStringMatchers:
#- AD0820DC40D6FEF9FDFC59AEA040A776
#- OUTFIT_QM_010_NAME

# Look for assets that include these search terms in their binary data converted to ascii
#searchBinaryAsciiMatchers:
#- SVR_F17

# Whether to search CustomizationItemDB assets for models and attachments
searchingSlots: true

# Continue where you left off in a previous search.
#searchResume:
#  pakchunkRelStemPath: pakchunk14-WindowsNoEditor
#  assetPath: Characters/Campers/Finland/Models/Heads/ACC/Blueprints/AB_FS_Hat_ACC006

'''
  )

def getContentDirRelativePath(path):
    path = normPath(path)
    start = '/Content/'
    if path.startswith(start):
        return path[len(start):]


def isValidSettingsFilename(filename):
  filenameLower = filename.lower()
  return (
      filenameLower.endswith('.yaml')
      # TODO: remove
      and (True or filenameLower.startswith(DefaultSettingsFileStem))
      and not filename.startswith('.')
      and f'_{CustomizationItemDbAssetName}' not in filename
      and not filename.startswith('searchAssetMatches-')
      and not filename.startswith('searchNameMapMatches-')
      and not filename.startswith('searchJsonStringMatches-')
      and not filename.startswith('searchBinaryAsciiMatches-')
      and not filename.endswith('-results.yaml')
      and not filename.endswith('-altered.yaml')
      and not filename.endswith('-unaltered.yaml')
  )


def findSettingsFiles(dir='.'):
    for entry in os.scandir(dir):
        if isValidSettingsFilename(entry.name):
            yield entry.name


def getResultsFilePath(settingsFilePath):
    return f"{settingsFilePath.removesuffix('.yaml')}-results.yaml"


def getEnabledDisabledStr(flag):
    return 'enabled' if flag else 'disabled'
