from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from config import settings

import json, time, os, platform, re, logging
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.CrawlingManager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)

SITE_NAME = "DIGITAL INSIGHT"
URL = "https://ditoday.com/article/page/{page_num}/?order=latest"


def crawling(driver: CrawlingManager):

    page_num = 0
    isLoop = True
    limiter = ResultLimiter()

    while isLoop:
        page_num += 1
        logger.debug(f"page_num : {page_num}")
        driver.browser.get(URL.format(page_num=page_num))

        # 로드완료되었는지 확인
        WebDriverWait(driver.browser, 10).until(wait_ready_state())

        rows = driver.browser.find_elements(By.CSS_SELECTOR, "li.article-loop-item")
        for row in rows:
            try:
                start_time = time.time()  # 시작 시간 기록

                date_text = row.find_element(
                    By.CSS_SELECTOR, "div.entry-meta > div.entry-info > span.entry-date"
                ).text.strip()

                if not is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
                    logger.debug(
                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                    )
                    isLoop = False
                    break

                title_el = row.find_element(
                    By.CSS_SELECTOR, "div.entry-meta > h3.entry-title > a"
                )

                href = title_el.get_attribute("href")
                title = title_el.text.strip()

                result_item = make_result(
                    SITE_NAME,
                    None,
                    title,
                    href,
                    replace_date(date_text),
                    driver.getIdx(),
                )

                if not limiter.append(result_item):
                    logger.debug(f"🛑 디버그 모드: 수집 제한 도달, 중단")
                    isLoop = False
                    break

                elapsed_time = time.time() - start_time  # 경과 시간 계산
                logger.debug(f"⏱️ {href} 소요 시간: {elapsed_time:.2f}초")
            except Exception as e:
                logger.error(f"❌ 오류 발생: {e}")
                continue

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
