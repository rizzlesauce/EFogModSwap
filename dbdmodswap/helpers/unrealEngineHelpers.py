import os

from .pathHelpers import normPath

UassetFilenameSuffix = '.uasset'
UnrealEngineCookedSplitFileExtensions = {UassetFilenameSuffix, '.ubulk', '.uexp'}


def getUnrealProjectCookedContentDir(unrealProjectDir, platform, gameName):
    return normPath(os.path.join(unrealProjectDir, 'Saved', 'Cooked', platform, gameName, 'Content'))
