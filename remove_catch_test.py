import shutil
import os
from crawler.profile_manager import (
    load_profile,
    save_profile,
    clean_cache,
    remove_history,
)


site = "naver"
profile_path = load_profile(site)
# 크롤링 종료 후
clean_cache(profile_path)
remove_history(profile_path)
save_profile(site)
