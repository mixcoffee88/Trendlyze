import os
import platform
from pathlib import Path
from dotenv import load_dotenv

# ─── .env 로딩 ──────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)

# ─── 루트 및 시스템 정보 ────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OS_NAME = platform.system().lower()

# ─── Chrome 드라이버 및 바이너리 경로 ──
CHROME_DRIVER_PATH = (
    PROJECT_ROOT
    / "driver"
    / OS_NAME
    / "chromedriver"
    / ("chromedriver.exe" if OS_NAME == "windows" else "chromedriver")
)

CHROME_BINARY_PATH = (
    PROJECT_ROOT
    / "driver"
    / OS_NAME
    / "chrome"
    / ("chrome.exe" if OS_NAME == "windows" else "chrome")
)

USER_DATA_DIR = (
    "C:/tmp/tmp/chrome-profile" if OS_NAME == "windows" else "/tmp/chrome-profile"
)

# ─── LLM 설정 ──────────────────────────
# LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "")
# HF_MODEL = os.getenv("HF_MODEL", "")

# ─── 공통 설정 ─────────────────────────
HEADLESS_MODE = True
IS_CRAWLING_LIMIT = os.getenv("IS_CRAWLING_LIMIT", "true").lower() == "true"
CRAWLING_LIMIT = int(os.getenv("CRAWLING_LIMIT", 5))
CRAWLING_LIMIT_DAY = int(os.getenv("CRAWLING_LIMIT_DAY", 30))
# LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
# WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", 10))

# ─── 경로 설정 ─────────────────────────
DATA_DIR = "data"
CRAWL_DATA_DIR = "crawl"
ANALYZE_DATA_DIR = "analyze"
REPORT_DIR = "reports"

# ─── AWS 설정 ─────────────────────────
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "")
AWES_S3_BUCKET_NAME = os.getenv("AWES_S3_BUCKET_NAME", "")
