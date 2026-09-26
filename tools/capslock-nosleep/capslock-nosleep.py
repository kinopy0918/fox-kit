#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""スリープ抑止を 2 系統に分けて自動で出し入れする常駐デーモン。

  1. CapsLock が ON の間だけ pmset -a disablesleep 1
     → 「フタを閉じても寝ない」のトグル。これは CapsLock だけで決まる。
     この状態でフタを閉じるとバックライトも消えなくなるので、フタが閉じている間は
     pmset displaysleepnow を撃って画面だけ消す。
  2. Antigravity IDE が起動中の間だけ caffeinate -i を保持
     → フタが開いている限りアイドルスリープしない (エージェントの作業が止まらない)。
       アイドル抑止なのでフタを閉じれば普通に寝る。

root の LaunchDaemon として動かす。macOS 標準の /usr/bin/python3 だけで動く
(Homebrew や外部モジュールに依存しない)。
"""

import ctypes
import os
import signal
import subprocess
import sys
import time

POLL_SEC = 1.0
PMSET = "/usr/bin/pmset"
PS = "/bin/ps"
CAFFEINATE = "/usr/bin/caffeinate"
IOREG = "/usr/sbin/ioreg"

# disablesleep 1 の間はフタを閉じても画面が消えないので、閉じている間は定期的に
# displaysleepnow を撃ち直す (何かが画面を点け直しても再度消すため)
DISPLAY_PUSH_SEC = 15

# Antigravity IDE の本体プロセス (ヘルパーではなくメインの Electron) だけを見る。
# pgrep -f はこの Electron の argv を拾えないので ps の comm (実行ファイルの絶対パス) で判定する。
ANTIGRAVITY_COMM = "/Applications/Antigravity IDE.app/Contents/MacOS/Electron"
# プロセス走査は 1 秒ごとにやる必要がないので間引く
ANTIGRAVITY_EVERY = 5

kIOHIDParamConnectType = 1
kIOHIDCapsLockState = 1

iokit = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
libc = ctypes.CDLL(None)

iokit.IOServiceMatching.restype = ctypes.c_void_p
iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
iokit.IOServiceGetMatchingService.restype = ctypes.c_uint32
iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
iokit.IOServiceOpen.argtypes = [
    ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
]
iokit.IOServiceClose.argtypes = [ctypes.c_uint32]
iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]
iokit.IOHIDGetModifierLockState.argtypes = [
    ctypes.c_uint32, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)
]

MACH_TASK_SELF = ctypes.c_uint32.in_dll(libc, "mach_task_self_").value


def log(msg):
    print("%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    sys.stdout.flush()


def open_hid():
    """IOHIDSystem への param connect を開く。失敗したら None。"""
    service = iokit.IOServiceGetMatchingService(0, iokit.IOServiceMatching(b"IOHIDSystem"))
    if not service:
        return None
    conn = ctypes.c_uint32(0)
    kr = iokit.IOServiceOpen(service, MACH_TASK_SELF, kIOHIDParamConnectType, ctypes.byref(conn))
    iokit.IOObjectRelease(service)
    if kr != 0:
        log("IOServiceOpen failed: 0x%08x" % (kr & 0xFFFFFFFF))
        return None
    return conn.value


def caps_on(conn):
    """CapsLock の状態。読めなかったら None (呼び出し側で接続を張り直す)。"""
    state = ctypes.c_bool(False)
    kr = iokit.IOHIDGetModifierLockState(conn, kIOHIDCapsLockState, ctypes.byref(state))
    if kr != 0:
        return None
    return state.value


def antigravity_running():
    """Antigravity IDE の本体プロセスが生きていれば True。"""
    try:
        out = subprocess.check_output([PS, "-axo", "comm="], stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError) as exc:
        log("ps failed: %s" % exc)
        return False
    for line in out.decode("utf-8", "replace").splitlines():
        if line.strip() == ANTIGRAVITY_COMM:
            return True
    return False


def lid_closed():
    """フタが閉じていれば True。IOPMrootDomain の AppleClamshellState を見る。"""
    try:
        out = subprocess.check_output(
            [IOREG, "-r", "-k", "AppleClamshellState", "-d", "4"], stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError) as exc:
        log("ioreg failed: %s" % exc)
        return False
    for line in out.decode("utf-8", "replace").splitlines():
        if "AppleClamshellState" in line:
            return line.strip().endswith("Yes")
    return False


def display_sleep_now():
    subprocess.call([PMSET, "displaysleepnow"])


def set_disablesleep(on, reason):
    subprocess.call([PMSET, "-a", "disablesleep", "1" if on else "0"])
    log("pmset -a disablesleep %d  (%s)" % (1 if on else 0, reason))


class IdleGuard(object):
    """caffeinate -i を子プロセスとして保持する (アイドルスリープだけ抑止)。

    フタ閉じスリープには効かないので、disablesleep とは独立に出し入れできる。
    """

    def __init__(self):
        self.proc = None

    def held(self):
        if self.proc is None:
            return False
        if self.proc.poll() is not None:  # 落ちていたら保持していない扱い
            self.proc = None
            return False
        return True

    def acquire(self, reason):
        if self.held():
            return
        try:
            self.proc = subprocess.Popen([CAFFEINATE, "-i"])
        except OSError as exc:
            log("caffeinate failed: %s" % exc)
            self.proc = None
            return
        log("caffeinate -i started pid=%d  (%s)" % (self.proc.pid, reason))

    def release(self, reason):
        if not self.held():
            self.proc = None
            return
        pid = self.proc.pid
        try:
            self.proc.terminate()
            self.proc.wait()
        except OSError as exc:
            log("caffeinate terminate failed: %s" % exc)
        self.proc = None
        log("caffeinate -i stopped pid=%d  (%s)" % (pid, reason))


_stop = False


def _handle_signal(signum, frame):
    global _stop
    _stop = True


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if os.geteuid() != 0:
        log("must run as root (pmset disablesleep requires root)")
        return 1

    conn = None
    applied = None  # 現在 pmset に反映済みの disablesleep 状態
    idle = IdleGuard()
    ag = False      # Antigravity 起動中か (ANTIGRAVITY_EVERY 秒ごとに更新)
    was_closed = False   # 前回のフタの状態 (CapsLock ON のときだけ見る)
    last_push = 0.0      # 最後に displaysleepnow を撃った時刻
    tick = 0

    log("started (poll=%.1fs)" % POLL_SEC)
    while not _stop:
        if conn is None:
            conn = open_hid()
            if conn is None:
                time.sleep(POLL_SEC)
                continue
            log("IOHIDSystem connected")

        caps = caps_on(conn)
        if caps is None:
            log("read failed; reconnecting")
            iokit.IOServiceClose(conn)
            conn = None
            time.sleep(POLL_SEC)
            continue

        # (1) フタ閉じスリープの無効化は CapsLock だけで決める
        state = bool(caps)
        if state != applied:
            set_disablesleep(state, "CapsLock %s" % ("ON" if caps else "OFF"))
            applied = state

        # (1b) CapsLock ON でフタを閉じている間は、画面だけ消す
        if caps:
            closed = lid_closed()
            now = time.time()
            if closed and not was_closed:
                display_sleep_now()
                last_push = now
                log("lid closed (CapsLock ON) -> pmset displaysleepnow")
            elif closed and now - last_push >= DISPLAY_PUSH_SEC:
                display_sleep_now()   # 点け直されていたらまた消す (ログは出さない)
                last_push = now
            elif was_closed and not closed:
                log("lid opened")
            was_closed = closed
        else:
            was_closed = False

        # (2) Antigravity が動いている間はアイドルスリープさせない
        if tick % ANTIGRAVITY_EVERY == 0:
            ag = antigravity_running()
            if ag:
                idle.acquire("Antigravity running")
            else:
                idle.release("Antigravity not running")
        tick += 1

        time.sleep(POLL_SEC)

    # 終了時は必ず通常のスリープ挙動に戻す
    if applied:
        set_disablesleep(False, "daemon stopping")
    idle.release("daemon stopping")
    if conn is not None:
        iokit.IOServiceClose(conn)
    log("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
