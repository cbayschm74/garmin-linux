"""Per-file progress for repeated planning and installation checks."""
from time import monotonic


def file_progress(callback, phase, path, total=None):
    size = path.stat().st_size if total is None else total
    started = monotonic()
    def report(done, *_):
        if callback:
            callback(dict(phase=phase, filename=path.name, file_bytes_done=done,
                          file_bytes_total=size, file_index=1, file_count=1,
                          completed_bytes=done, total_work_bytes=size,
                          phase_elapsed_seconds=monotonic() - started, scope='file'))
    report(0)
    return report


def hash_file(path, hasher, callback, phase):
    if callback is None:
        return hasher(path)
    report = file_progress(callback, phase, path)
    done = 0
    def advance(amount):
        nonlocal done
        done += amount
        report(done)
    return hasher(path, progress=advance)


def phase_progress(callback, phase):
    if callback:
        callback(dict(phase=phase, filename='', file_bytes_done=0,
                      file_bytes_total=0, completed_bytes=0, total_work_bytes=0,
                      file_index=0, file_count=0, scope='file'))
