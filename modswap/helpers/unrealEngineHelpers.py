import os

from .pathHelpers import normPath

UassetJsonSuffix = '.uasset.json'

UassetFilenameSuffix = '.uasset'
UexpFilenameSuffix = '.uexp'
UbulkFilenameSuffix = '.ubulk'
UnrealEngineCookedSplitFileExtensions = {UassetFilenameSuffix, UbulkFilenameSuffix, UexpFilenameSuffix}
OtherAssetFileExtensions = {
    '.bnk',
    '.json',
    '.xml',
    '.wem',
}
AllAssetFileExtensions = UnrealEngineCookedSplitFileExtensions.union(OtherAssetFileExtensions)

def getUnrealProjectCookedContentDir(unrealProjectDir, platform, gameName):
    return normPath(os.path.join(unrealProjectDir, 'Saved', 'Cooked', platform, gameName, 'Content'))


def getAssetStemPathInfo(assetFilePath):
    result = {}
    assetPathLower = assetFilePath.lower()
    stemPath = None
    assetSuffix = None
    if assetPathLower.endswith(UassetJsonSuffix):
        stemPath = assetFilePath[:-len(UassetJsonSuffix)]
        assetSuffix = UassetFilenameSuffix
    else:
        for suffix in AllAssetFileExtensions:
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
    results = []
    result = getAssetStemPathInfo(assetFilePath)
    if result:
        if result['suffix'] in UnrealEngineCookedSplitFileExtensions:
            for suffix in UnrealEngineCookedSplitFileExtensions:
                results.append(f"{result['stemPath']}{suffix}")
        else:
            results.append(result)

    return results
