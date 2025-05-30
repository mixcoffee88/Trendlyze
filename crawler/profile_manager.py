import os, shutil, subprocess

EFS_BASE = "/mnt/efs/profiles"


def load_profile(site: str):
    src = os.path.join(EFS_BASE, site, "user-data-dir")
    dst = f"/tmp/{site}_profile"
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def save_profile(site: str):
    src = f"/tmp/{site}_profile"
    dst = os.path.join(EFS_BASE, site, "user-data-dir")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def clean_cache(profile_path: str):
    cache_path = os.path.join(profile_path, "Default", "Cache")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)


def remove_history(profile_path: str):
    history_files = ["History", "History-journal", "Visited Links", "Top Sites"]
    for f in history_files:
        path = os.path.join(profile_path, "Default", f)
        if os.path.exists(path):
            os.remove(path)
