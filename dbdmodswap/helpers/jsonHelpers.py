import json


def jsonifyDataRecursive(value, isKey=False):
    if isinstance(value, dict):
        newValue = {jsonifyDataRecursive(k, isKey=True): jsonifyDataRecursive(v) for k, v in value.items()}
    elif isinstance(value, set) or isinstance(value, frozenset):
        listVersion = sorted([jsonifyDataRecursive(v, isKey=isKey) for v in value], key=lambda x: x.upper() if isinstance(x, str) else x)
        if isKey:
            newValue = ','.join(listVersion)
        else:
            newValue = listVersion
    else:
        newValue = value

    return newValue


class JsonSetEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, set) or isinstance(value, frozenset):
            return sorted(list(value), key=lambda v: v.upper() if isinstance(v, str) else v)
        return json.JSONEncoder.default(self, value)


def jsonDump(value, stream=None, pretty=False):
    indent = 2 if pretty else None
    if stream:
        return json.dump(value, stream, indent=indent, cls=JsonSetEncoder)
    else:
        return json.dumps(value, indent=indent, cls=JsonSetEncoder)
