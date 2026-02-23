"""Win32 SendInput 直接输入，比 pyautogui 快得多。"""
import ctypes
import ctypes.wintypes as wt

user32 = ctypes.windll.user32

# ---- 常量 ----
INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_RIGHTDOWN   = 0x0008
MOUSEEVENTF_RIGHTUP     = 0x0010
MOUSEEVENTF_MIDDLEDOWN  = 0x0020
MOUSEEVENTF_MIDDLEUP    = 0x0040
MOUSEEVENTF_WHEEL       = 0x0800
MOUSEEVENTF_ABSOLUTE    = 0x8000
KEYEVENTF_KEYUP         = 0x0002
KEYEVENTF_UNICODE       = 0x0004

# ---- 结构体 ----
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(wt.ULONG))]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("_u", _INPUT_UNION)]


def _screen_to_absolute(x: int, y: int):
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    return int(x * 65535 / (sw - 1)), int(y * 65535 / (sh - 1))


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def mouse_move(x: int, y: int):
    ax, ay = _screen_to_absolute(x, y)
    inp = INPUT(type=INPUT_MOUSE,
                _u=_INPUT_UNION(mi=MOUSEINPUT(dx=ax, dy=ay, mouseData=0,
                    dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, time=0,
                    dwExtraInfo=None)))
    _send(inp)


def mouse_click(x: int, y: int, button: str = "left"):
    mouse_move(x, y)
    ax, ay = _screen_to_absolute(x, y)
    if button == "right":
        down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
    elif button == "middle":
        down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
    else:
        down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

    def _mi(flag):
        return INPUT(type=INPUT_MOUSE,
                     _u=_INPUT_UNION(mi=MOUSEINPUT(dx=ax, dy=ay, mouseData=0,
                         dwFlags=flag | MOUSEEVENTF_ABSOLUTE, time=0, dwExtraInfo=None)))
    _send(_mi(down_flag), _mi(up_flag))


def mouse_double_click(x: int, y: int):
    mouse_click(x, y)
    mouse_click(x, y)


def mouse_scroll(x: int, y: int, clicks: int):
    mouse_move(x, y)
    ax, ay = _screen_to_absolute(x, y)
    inp = INPUT(type=INPUT_MOUSE,
                _u=_INPUT_UNION(mi=MOUSEINPUT(dx=ax, dy=ay,
                    mouseData=wt.DWORD(clicks * 120),
                    dwFlags=MOUSEEVENTF_WHEEL | MOUSEEVENTF_ABSOLUTE,
                    time=0, dwExtraInfo=None)))
    _send(inp)


# VK 码映射（常用键）
_VK_MAP = {
    "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "tab": 0x09, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
    "space": 0x20, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "lwin": 0x5B,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C,
    "m": 0x4D, "n": 0x4E, "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
}


def _vk(key: str) -> int:
    k = key.lower()
    if k in _VK_MAP:
        return _VK_MAP[k]
    # 单字符直接用 VkKeyScanA
    if len(k) == 1:
        return user32.VkKeyScanA(ord(k)) & 0xFF
    return 0


def key_down(key: str):
    vk = _vk(key)
    if not vk:
        return
    inp = INPUT(type=INPUT_KEYBOARD,
                _u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0, time=0, dwExtraInfo=None)))
    _send(inp)


def key_up(key: str):
    vk = _vk(key)
    if not vk:
        return
    inp = INPUT(type=INPUT_KEYBOARD,
                _u=_INPUT_UNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)))
    _send(inp)


def hotkey(*keys):
    for k in keys:
        key_down(k)
    for k in reversed(keys):
        key_up(k)


def key_press(key: str):
    key_down(key)
    key_up(key)


def type_text(text: str):
    """用 Unicode SendInput 输入任意文字，支持中文，无需剪贴板。"""
    inputs = []
    for ch in text:
        scan = ord(ch)
        inputs.append(INPUT(type=INPUT_KEYBOARD,
            _u=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=scan,
                dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=None))))
        inputs.append(INPUT(type=INPUT_KEYBOARD,
            _u=_INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=scan,
                dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=None))))
    # SendInput 每批最多 ~500 个，分批发送
    batch = 64
    for i in range(0, len(inputs), batch):
        arr = (INPUT * len(inputs[i:i+batch]))(*inputs[i:i+batch])
        user32.SendInput(len(inputs[i:i+batch]), arr, ctypes.sizeof(INPUT))
