import ctypes
try:
    SHEmptyRecycleBin = ctypes.windll.shell32.SHEmptyRecycleBinW
    SHEmptyRecycleBin(None, None, 1 | 2 | 4)
    print("Success")
except Exception as e:
    print(f"Error: {e}")
