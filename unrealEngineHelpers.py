import os

from pathHelpers import normPath

UnrealEngineCookedSplitFileExtensions = {'.uasset', '.ubulk', '.uexp'}


def getUnrealProjectCookedContentDir(unrealProjectDir, platform, gameName):
    return normPath(os.path.join(unrealProjectDir, 'Saved', 'Cooked', platform, gameName, 'Content'))
