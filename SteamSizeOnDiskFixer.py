import os
import re
import ctypes

# All known Steam library paths (to their steamapps folders)
STEAM_LIBRARIES = [
    r"C:\Program Files (x86)\Steam\steamapps",
    r"F:\SteamLibrary\steamapps",
    r"E:\Games\SteamLibrary\steamapps",
    r"D:\SteamLibrary\steamapps"  # Make sure this matches your folder names
]

def parse_acf(acf_path):
    """Parse .acf into a flat dictionary."""
    with open(acf_path, encoding='utf-8') as f:
        text = f.read()

    flat = {}
    for match in re.finditer(r'"([^"]+)"\s+"([^"]+)"', text):
        flat[match.group(1)] = match.group(2)
    return flat

def update_acf(acf_path, new_size):
    """Update the SizeOnDisk field in an ACF file."""
    with open(acf_path, encoding='utf-8') as f:
        content = f.read()

    if '"SizeOnDisk"' in content:
        content = re.sub(r'"SizeOnDisk"\s*"\d+"', f'\t"SizeOnDisk"\t"{new_size}"', content)
    else:
        content = content.rstrip()[:-1] + f'\n\t"SizeOnDisk"\t"{new_size}"\n' + '}'

    with open(acf_path, "w", encoding='utf-8') as f:
        f.write(content)

def get_file_size_on_disk(path):
    """Return size on disk using Windows API (GetCompressedFileSizeW)."""
    if not os.path.exists(path):
        return 0
    try:
        GetCompressedFileSizeW = ctypes.windll.kernel32.GetCompressedFileSizeW
        GetCompressedFileSizeW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
        high = ctypes.c_ulong(0)
        low = GetCompressedFileSizeW(path, ctypes.byref(high))
        size = (high.value << 32) + low
        return size
    except Exception as e:
        print(f"Error getting disk size for {path}: {e}")
        return 0

def get_folder_size(path):
    """Calculate size on disk for all files in a folder."""
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

        try:
            files = os.listdir(library)
        except Exception as e:
            print(f"❌ Error listing directory {library}: {e}")
            continue

        for file in files:
            if file.startswith("appmanifest_") and file.endswith(".acf"):
                acf_path = os.path.join(library, file)
                acf_data = parse_acf(acf_path)
                install_dir = acf_data.get("installdir")

                if not install_dir:
                    print(f"❓ No installdir in {file}")
                    continue

                # Correct: steamapps/common/GameFolder
                common_path = os.path.join(library, "common")
                game_path = os.path.join(common_path, install_dir)

                if os.path.isdir(game_path):
                    size = get_folder_size(game_path)
                    print(f"✅ Updating {file} for '{install_dir}' - Size on disk: {size / 1024**3:.2f} GB")
                    update_acf(acf_path, size)
                else:
                    print(f"🚫 Game folder not found for {install_dir} at {game_path}")

if __name__ == "__main__":
    main()
