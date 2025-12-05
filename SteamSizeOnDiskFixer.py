import os
import re
import shutil
import ctypes
from ctypes import wintypes

# Paths to your Steam libraries (steamapps folders)
STEAM_LIBRARIES = [
    r"C:\Program Files (x86)\Steam\steamapps",
    r"F:\SteamLibrary\steamapps",
    r"E:\Games\SteamLibrary\steamapps",
    r"D:\SteamLibrary\steamapps"
]

def parse_acf(acf_path):
    """Parse .acf into a flat dictionary of key/value pairs."""
    with open(acf_path, encoding='utf-8') as f:
        text = f.read()
    return {m.group(1): m.group(2) for m in re.finditer(r'"([^"]+)"\s+"([^"]+)"', text)}

def backup_acf(acf_path):
    """Create a backup copy of the ACF file before modifying."""
    backup_path = acf_path + ".bak"
    if not os.path.exists(backup_path):
        shutil.copy2(acf_path, backup_path)
        print(f"📦 Backup created: {backup_path}")
    else:
        print(f"📦 Backup already exists: {backup_path}")

def update_acf(acf_path, new_size_bytes):
    """Update or insert the SizeOnDisk field in an ACF file (in bytes)."""
    backup_acf(acf_path)

    with open(acf_path, encoding='utf-8') as f:
        content = f.read()

    # allow replacing negative values too
    if '"SizeOnDisk"' in content:
        # Use a replacement function to avoid group reference issues
        def repl(match):
            return f'{match.group(1)}{new_size_bytes}{match.group(2)}'

        content = re.sub(
            r'("SizeOnDisk"\s*")-?\d+(")',
            repl,
            content
        )
    else:
        # Insert before final closing brace
        content = re.sub(
            r'}\s*$',
            f'\t"SizeOnDisk"\t"{new_size_bytes}"\n}}',
            content
        )

    with open(acf_path, "w", encoding='utf-8') as f:
        f.write(content)

def get_file_size_on_disk(path):
    """Return size on disk using Windows API (GetCompressedFileSizeW)."""
    if not os.path.exists(path):
        return 0
    try:
        GetCompressedFileSizeW = ctypes.windll.kernel32.GetCompressedFileSizeW
        GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        # restype as DWORD (unsigned 32-bit)
        GetCompressedFileSizeW.restype = wintypes.DWORD

        high = wintypes.DWORD(0)
        ctypes.windll.kernel32.SetLastError(0)
        low = GetCompressedFileSizeW(path, ctypes.byref(high))

        # Check for error condition
        if int(low) == 0xFFFFFFFF:
            err = ctypes.windll.kernel32.GetLastError()
            if err != 0:
                raise OSError(f"GetCompressedFileSizeW failed with error {err}")

        # Force unsigned 32-bit values and combine into unsigned 64-bit
        low_u = ctypes.c_uint32(int(low)).value
        high_u = ctypes.c_uint32(int(high.value)).value
        size = (high_u << 32) | low_u
        return int(size)
    except Exception as e:
        # fallback to logical file size if API fails
        try:
            return os.path.getsize(path)
        except Exception:
            print(f"Error getting disk size for {path}: {e}")
            return 0

def get_folder_size(path):
    """Calculate size on disk for all files in a folder (bytes)."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total_size += get_file_size_on_disk(fp)
    return total_size

def main():
    for library in STEAM_LIBRARIES:
        if not os.path.isdir(library):
            print(f"⚠️ Skipping missing path: {library}")
            continue

        for file in os.listdir(library):
            if file.startswith("appmanifest_") and file.endswith(".acf"):
                acf_path = os.path.join(library, file)
                acf_data = parse_acf(acf_path)

                appid = acf_data.get("appid")
                install_dir = acf_data.get("installdir")

                if not install_dir:
                    print(f"❓ No installdir in {file}")
                    continue

                game_path = os.path.join(library, "common", install_dir)

                if os.path.isdir(game_path):
                    size_bytes = get_folder_size(game_path)
                    print(f"✅ AppID {appid} ({install_dir}) - Actual size: {size_bytes / 1024**3:.2f} GB ({size_bytes} bytes)")
                    update_acf(acf_path, size_bytes)
                else:
                    print(f"🚫 Game folder not found for {install_dir} at {game_path}")

if __name__ == "__main__":
    main()