import subprocess


def runCall(args, cwd=None, shell=False):
    quoted = [f'"{arg}"' for arg in args]
    try:
        code = subprocess.call(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, shell=shell)
        if code:
            raise ValueError(f'subprocess returned error exit code: {code}')
    except:
        raise ValueError(f'subprocess call failed: cwd="{cwd}" {" ".join(quoted)}')
