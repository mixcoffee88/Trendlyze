from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

from config import settings

from urllib.parse import urlparse
import json, time, os, platform, re, logging, random
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.crawling_manager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)

SITE_NAME = "SAMSUNG SDS"
DOMAIN = "https://www.samsungsds.com/kr/insights/index.html"
URL = "https://www.samsungsds.com/{catCd}"
TARGET_LIST = [
    {"catCd": "/kr/insights/insights.txt?q=", "catNm": "인사이드 리포트"},
    {"catCd": "/kr/techreport/data.txt", "catNm": "클라우드 기술 백서"},
    {"catCd": "/kr/case-study/data.txt", "catNm": "고객 사례"},
]


def crawling(driver: CrawlingManager):

    limiter = ResultLimiter()

    # driver.browser.get(URL.format(catCd=target["catCd"]))
    driver.browser.get(DOMAIN)
    WebDriverWait(driver.browser, 10).until(wait_ready_state())

    for target in TARGET_LIST:
        logger.debug(f"{target['catNm']} 진행 시작")
        full_url = URL.format(catCd=target["catCd"])
        if TARGET_LIST[0]["catNm"] == target["catNm"]:
            random_number = random.randint(1000000, 9999999)
            full_url = "{}{}".format(full_url, random_number)

        driver.browser.get(full_url)
        time.sleep(1)
        body_text = driver.browser.find_element(
            "tag name", "pre"
        ).text  # JSON은 <pre>로 감싸져 반환됨
        json_data = json.loads(body_text)

        items = json_data if isinstance(json_data, list) else json_data.get("data", [])

        for item in items:
            try:

                title = item.get("title", "").strip()
                href = item.get("linkUrl") or item.get("detailLink")
                date_text = (
                    item.get("releaseDate")
                    or item.get("date", "")
                    or extract_date_from_thumb_url(item.get("thumbImg", ""))
                )

                if not (title and href):
                    continue  # 필수 필드가 없으면 skip

                if not is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
                    logger.debug(
                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                    )
                    break

                result_item = make_result(
                    SITE_NAME,
                    target,
                    title,
                    f"https://www.samsungsds.com{href}",
                    replace_date(date_text),
                    driver.getIdx(),
                )
                if not limiter.append(result_item):
                    logger.debug(
                        f"🛑 디버그 모드: {target['catCd']} 수집 제한 도달, 중단"
                    )
                    break
            except Exception as e:
                logger.error(f"오류 발생: {e} - {item}", exc_info=True)
                continue
        time.sleep(1)

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)


def extract_date_from_thumb_url(url: str) -> str:
    match = re.search(r"queryString=(\d{8})", url)
    if match:
        return match.group(1)
    return ""
