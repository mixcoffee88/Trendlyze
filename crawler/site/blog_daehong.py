from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from config import settings

from urllib.parse import urlparse
import json, time, os, platform, re, logging
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.CrawlingManager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)
SITE_NAME = "대홍기획 블로그"
URL = "https://blog.daehong.com/category/{catCd}?page={page_num}"
VIEW_URL = "https://blog.daehong.com/{id}"
TARGET_LIST = [
    {"catCd": "DIGGING/d-Issue", "catNm": "DIGGING d-Issue"},
    {"catCd": "DIGGING/Brand", "catNm": "DIGGING Brand"},
    {"catCd": "DIGGING/Trend", "catNm": "DIGGING Trend"},
    {"catCd": "DIGGING/Editor%20X", "catNm": "DIGGING Editor X"},
    {"catCd": "WORK/Campaign", "catNm": "WORK Campaign"},  #
    {"catCd": "WORK/Insight", "catNm": "WORK Insight"},
    {"catCd": "WORK/AD%20Note", "catNm": "WORK AD Note"},  #
    {"catCd": "INSIDE/d-Culture", "catNm": "INSIDE d-Culture"},
    {"catCd": "INSIDE/Play", "catNm": "INSIDE Play"},
    {"catCd": "INSIDE/Story", "catNm": "INSIDE Story"},
    {"catCd": "INSIDE/NEWS", "catNm": "INSIDE NEWS"},
]


def crawling(driver: CrawlingManager):

    parsed = urlparse(URL)
    limiter = ResultLimiter()

    for target in TARGET_LIST:
        logger.debug(f"{target['catNm']} 진행 시작")
        is_loop = True
        page_num = 0
        while is_loop:
            page_num += 1
            logger.debug(f"{target['catNm']} / {page_num} 진행 시작")
            if target["catCd"] == TARGET_LIST[0]["catCd"] and page_num == 1:
                driver.browser.execute_script(
                    f"window.open('{parsed.scheme}://{parsed.netloc}', '_blank');"
                )
                tabs = driver.browser.window_handles
                time.sleep(0.5)

            WebDriverWait(driver.browser, 5).until(lambda d: len(d.window_handles) >= 2)

            driver.browser.switch_to.window(tabs[0])  # 첫번째 탭에서 파싱
            time.sleep(0.5)

            driver.browser.get(URL.format(catCd=target["catCd"], page_num=page_num))
            WebDriverWait(driver.browser, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.link_post"))
            )

            rows = driver.browser.find_elements(By.CSS_SELECTOR, ".link_post")
            hrefs = [el.get_attribute("href") for el in rows]
            for href in hrefs:
                try:
                    logger.debug(f"🔗 [{target['catNm']}] Page {page_num}: {href}")
                    driver.browser.switch_to.window(tabs[1])  # 두번째 탭에서 파싱
                    time.sleep(0.5)
                    driver.browser.get(href)
                    WebDriverWait(driver.browser, 10).until(wait_ready_state())

                    title = driver.browser.find_element(
                        By.CSS_SELECTOR, "#content > div > div.hgroup > h1"
                    ).text.strip()
                    date_text = driver.browser.find_element(
                        By.CSS_SELECTOR, "#content > div > div.hgroup > div > span.date"
                    ).text.strip()
                    if not is_within_days(
                        date_text, "%Y. %m. %d. %H:%M", settings.CRAWLING_LIMIT_DAY
                    ):
                        logger.debug(
                            f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                        )
                        is_loop = False
                        break

                    result_item = make_result(
                        SITE_NAME,
                        target,
                        title,
                        href,
                        replace_date(date_text, "%Y. %m. %d. %H:%M"),
                        driver.getIdx(),
                    )
                    if not limiter.append(result_item):
                        logger.debug(
                            f"🛑 디버그 모드: {target['catCd']} 수집 제한 도달, 중단"
                        )
                        is_loop = False
                        break
                except Exception as e:
                    logger.error(f"❌ 오류 발생: {e} \n URL: {href}")
                    continue

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
