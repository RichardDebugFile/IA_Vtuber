import ctypes
GWL_EXSTYLE=-20; WS_EX_LAYERED=0x80000; WS_EX_TRANSPARENT=0x20; WS_EX_TOOLWINDOW=0x80
SetWindowLong=ctypes.windll.user32.SetWindowLongW
GetWindowLong=ctypes.windll.user32.GetWindowLongW
SetWindowPos=ctypes.windll.user32.SetWindowPos
HWND_TOPMOST=-1; SWP_NOMOVE=0x2; SWP_NOSIZE=0x1; SWP_SHOWWINDOW=0x40

def make_toolwindow_clickthrough(hwnd:int):
    ex = GetWindowLong(hwnd, GWL_EXSTYLE)
    SetWindowLong(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
    SetWindowPos(hwnd, HWND_TOPMOST, 0,0,0,0, SWP_NOMOVE|SWP_NOSIZE|SWP_SHOWWINDOW)
