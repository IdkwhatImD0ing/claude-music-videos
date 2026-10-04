"""Keeps render processes from outliving their owner (no ghost renders, no orphaned Blenders).

Two mechanisms, started by `start()` at the top of tools/render.py:

1. **Job object.** Every child process adopted with `adopt(popen)` joins a Windows job object that has
   JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE. The job handle lives only in this process, so when this process ends for any
   reason (finished, killed by the task manager, killed with its agent), Windows kills every adopted child.
2. **Watchdog thread.** Every 2 s: if the STOP flag file exists, or the process that launched this one has exited
   (e.g. the agent's shell was killed), terminate the job and exit with code 3.

Pause everything:  create the flag  (`New-Item G:/video-renders/STOP`)    Resume: remove it.
The flag path can be changed with the RENDER_STOP_FILE environment variable. `blender/run.py` also checks the flag
before every frame, so a Blender started some other way stops at its next frame.

Background renders must be launched with the Bash tool's run_in_background, not with a trailing `&` inside a
foreground command: when that shell exits, the watchdog sees its launcher gone and stops the render.
"""
from __future__ import annotations

import os
import sys
import threading
import time

STOP_FILE = os.environ.get('RENDER_STOP_FILE', 'G:/video-renders/STOP')
_job = None
_started = False


def stop_requested() -> bool:
    return os.path.exists(STOP_FILE)


def _win():
    import ctypes
    from ctypes import wintypes
    return ctypes, wintypes


def _make_job():
    if os.name != 'nt':
        return None
    ctypes, wintypes = _win()
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                                                     'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class BASIC(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD),
                    ('SchedulingClass', wintypes.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BASIC), ('IoInfo', IO_COUNTERS),
                    ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]

    k32.CreateJobObjectW.restype = wintypes.HANDLE
    h = k32.CreateJobObjectW(None, None)
    if not h:
        return None
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    k32.SetInformationJobObject(wintypes.HANDLE(h), 9, ctypes.byref(info), ctypes.sizeof(info))  # 9 = Extended
    return h


def adopt(popen) -> None:
    """Tie a child (subprocess.Popen) to this process: it dies when this process dies."""
    if _job is None or os.name != 'nt':
        return
    ctypes, wintypes = _win()
    try:
        ctypes.windll.kernel32.AssignProcessToJobObject(wintypes.HANDLE(_job), wintypes.HANDLE(int(popen._handle)))
    except Exception:
        pass


def _kill_all_and_exit(reason: str) -> None:
    try:
        print(f'[procguard] {reason}: stopping this render and its Blender processes', flush=True)
    except Exception:
        pass
    if _job is not None and os.name == 'nt':
        ctypes, wintypes = _win()
        ctypes.windll.kernel32.TerminateJobObject(wintypes.HANDLE(_job), 3)
    os._exit(3)


def _parent_handle():
    if os.name != 'nt':
        return None
    ctypes, wintypes = _win()
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x00100000, False, os.getppid())  # SYNCHRONIZE: holding it pins the parent's identity
    return h or None


def _watch(parent) -> None:
    ctypes, wintypes = _win() if os.name == 'nt' else (None, None)
    while True:
        if stop_requested():
            _kill_all_and_exit(f'STOP flag {STOP_FILE}')
        if parent is not None:
            if ctypes.windll.kernel32.WaitForSingleObject(wintypes.HANDLE(parent), 0) == 0:  # WAIT_OBJECT_0: exited
                _kill_all_and_exit('its launcher exited')
        time.sleep(2.0)


def start() -> None:
    """Call once at startup. Refuses to start while the STOP flag exists."""
    global _job, _started
    if _started:
        return
    _started = True
    if stop_requested():
        print(f'[procguard] STOP flag {STOP_FILE} exists: not starting (remove it to resume)', flush=True)
        sys.exit(3)
    _job = _make_job()
    threading.Thread(target=_watch, args=(_parent_handle(),), daemon=True).start()
