import json

import yaml

from .jsonHelpers import jsonDump


def yamlDump(value, stream=None, customTypes=False):
    if customTypes:
        jsonStr = jsonDump(value)
        value = json.loads(jsonStr)

    return yaml.dump(value, stream=stream, default_flow_style=False, sort_keys=False)
