import requests

from modswap.metadata.programMetaData import (GithubProjectOwnerName,
                                              GithubProjectRepoName)


def getGithubProjectUrl():
    return f'https://github.com/{GithubProjectOwnerName}/{GithubProjectRepoName}'


def getGithubApiProjectUrl():
    return f'https://api.github.com/repos/{GithubProjectOwnerName}/{GithubProjectRepoName}'


def getGithubProjectReleasesUrl():
    return f'{getGithubProjectUrl()}/releases'


def getGithubProjectReleaseUrl(version=None):
    return f"{getGithubProjectReleasesUrl()}/{f'tags/v{version}' if version else 'latest'}"


def getLatestReleaseVersion():
    try:
        response = requests.get(f"{getGithubApiProjectUrl()}/releases/latest")
        return response.json()['name'].removeprefix('v')
    except:
        pass
