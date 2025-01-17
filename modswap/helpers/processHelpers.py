import asyncio
import subprocess


async def _readStream(stream, streamName, queue, process, data, stop):
    """Asynchronously read a stream and put its output into the queue."""
    while True:
        if data['shouldStop']:
            process.terminate()
            break
        line = await stream.readline()
        if not line:
            break
        decodedLine = line.decode('utf-8', errors='replace').rstrip('\n')
        await queue.put((streamName, decodedLine, stop))


async def _runCommandAsync(command, args, queue, cwd=None):
    """Run the command and read both stdout and stderr asynchronously."""
    process = await asyncio.create_subprocess_exec(
        command, *args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )

    data = {
        'shouldStop': False,
    }
    def stop():
        data['shouldStop'] = True

    await asyncio.gather(
        _readStream(process.stdout, 'stdout', queue, process, data, stop),
        _readStream(process.stderr, 'stderr', queue, process, data, stop)
    )

    returnCode = await process.wait()

    await queue.put(('return_code', returnCode, stop))


def runCommand(command, args, cwd=None):
    """Generator function that yields (streamName, line) tuples and the return code."""
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue()

    async def _internal():
        await _runCommandAsync(command, args, queue, cwd=cwd)
        await queue.put(None)

    loop.create_task(_internal())

    while True:
        item = loop.run_until_complete(queue.get())
        if item is None:
            break
        yield item


def run(args, cwd=None, shell=False):
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd, shell=shell)


def runCall(args, cwd=None, shell=False):
    try:
        code = subprocess.call(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd, shell=shell)
        if code:
            raise ValueError(f'subprocess returned error exit code: {code}')
    except:
        quoted = [f'"{arg}"' for arg in args]
        raise ValueError(f'subprocess call failed: cwd="{cwd}" {" ".join(quoted)}')
