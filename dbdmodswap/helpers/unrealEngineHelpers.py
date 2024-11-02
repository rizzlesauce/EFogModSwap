import os

from .pathHelpers import normPath

UassetFilenameSuffix = '.uasset'
UexpFilenameSuffix = '.uexp'
UbulkFilenameSuffix = '.ubulk'
UnrealEngineCookedSplitFileExtensions = {UassetFilenameSuffix, UbulkFilenameSuffix, UexpFilenameSuffix}


def getUnrealProjectCookedContentDir(unrealProjectDir, platform, gameName):
    return normPath(os.path.join(unrealProjectDir, 'Saved', 'Cooked', platform, gameName, 'Content'))


def getAssetStemPathInfo(assetFilePath):
    result = {}
    assetPathLower = assetFilePath.lower()
    stemPath = None
    assetSuffix = None
    for suffix in UnrealEngineCookedSplitFileExtensions:
        if assetPathLower.endswith(suffix):
            assetSuffix = suffix
            stemPath = assetFilePath[:-len(suffix)]
            break

    if stemPath:
        result = {
            'stemPath': stemPath,
            'suffix': assetSuffix,
        }

    return result


def getAssetSplitFilePaths(assetFilePath):
    """Paths may not exist"""
    result = getAssetStemPathInfo(assetFilePath)
    if result:
        result['splitPaths'] = [f'{result["stemPath"]}{suffix}' for suffix in UnrealEngineCookedSplitFileExtensions],

    return result
