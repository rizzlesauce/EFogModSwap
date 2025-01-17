import os

from .pathHelpers import normPath

UassetJsonSuffix = '.uasset.json'

UassetFilenameSuffix = '.uasset'
UmapFilenameSuffix = '.umap'
UexpFilenameSuffix = '.uexp'
UbulkFilenameSuffix = '.ubulk'
UfontFilenameSuffix = '.ufont'
UnrealEngineCookedSplitFileExtensions = {
    UassetFilenameSuffix,
    UmapFilenameSuffix,
    UbulkFilenameSuffix,
    UexpFilenameSuffix,
    UfontFilenameSuffix,
}
OtherAssetFileExtensions = {
    # sound bank and audio files
    '.bnk',
    '.wem',
    '.wav',
    #'.ogg',
    #'.mp3',
    #'.mp4',
    #'.mov',
    #'.wmv',
    #'.avi',
    # text files
    '.json',
    '.xml',
    '.csv',
    '.txt',
    # data files
    '.bin',
    '.dat',
    # shader files (possibly included)
    #'.shader',
    #'.ush',
    #'.usf',
    # scripts (uncommon)
    #'.lua',
    #'.py',
    # localization files
    '.locres',
    # config files
    '.ini',
    # font files
    #'.ttf',
    #'.otf',
    # backup files
    '.bak',
    # other files
    '.mat',
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
