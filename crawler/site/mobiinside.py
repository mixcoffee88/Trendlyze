from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from config import settings

import json, time, os, platform, re, logging
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.crawling_manager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)

SITE_NAME = "모비인사이드"
URL = "https://www.mobiinside.co.kr/{catCd}"
TARGET_LIST = [
    {
        "catCd": "menu-content/menu-content-marketing-brand",
        "catNm": "마케팅/브랜드",
    },
    {"catCd": "menu-content/menu-content-trend", "catNm": "트렌드"},
    {
        "catCd": "menu-content/menu-content-business-startup",
        "catNm": "비즈니스/스타트업",
    },
    {"catCd": "menu-content/menu-content-career", "catNm": "커리어"},
    {"catCd": "menu-content/menu-content-tech-ai", "catNm": "테크/AI"},
    {"catCd": "menu-content/menu-content-game", "catNm": "게임"},
    {"catCd": "menu-inside/menu-inside-studio", "catNm": "STUDIO"},
    {"catCd": "menu-inside/menu-inside-post", "catNm": "POST"},
    {"catCd": "menu-inside/menu-inside-landscape", "catNm": "랜드스케이프"},
    {"catCd": "menu-inside/menu-inside-insideranking", "catNm": "인사이드랭킹"},
    {"catCd": "news-3/보도자료", "catNm": "보도자료"},
    {"catCd": "news-3/global-2", "catNm": "GLOBAL"},
]


def crawling(driver: CrawlingManager):

    limiter = ResultLimiter()

    for target in TARGET_LIST:
        driver.browser.get(URL.format(catCd=target["catCd"]))

        isLoop = True
        # 첫번쨰 목록 요소 체크
        WebDriverWait(driver.browser, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.item-details"))
        )

        while isLoop:
            data_rows = driver.browser.find_elements(
                By.CSS_SELECTOR, "div.item-details"
            )
            last_row = data_rows[-1]
            last_row_date_text = last_row.find_element(
                By.CSS_SELECTOR, "div.td-module-meta-info time"
            ).get_attribute("datetime")

            if not is_within_days(last_row_date_text, day=settings.CRAWLING_LIMIT_DAY):
                logger.debug(
                    f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {last_row_date_text}"
                )
                isLoop = False
                break

            try:
                more_btn = driver.browser.find_element(
                    By.CSS_SELECTOR, "div.td-load-more-wrap > a"
                )
                more_btn.click()
                # visible 상태 될 때까지 대기
                WebDriverWait(driver.browser, 10).until(EC.visibility_of(more_btn))
            except Exception as e:
                logger.error(f"Load more 버튼 클릭 오류 : {e}")
                isLoop = False

        rows = driver.browser.find_elements(By.CSS_SELECTOR, "div.item-details")
        for row in rows:
            try:
                date_text = row.find_element(
                    By.CSS_SELECTOR, "div.td-module-meta-info time"
                ).get_attribute("datetime")

                if not is_within_days(date_text):
                    logger.debug(f"⏩ 무시 (30일 초과): {date_text}")
                    break

                news = row.find_element(By.CSS_SELECTOR, "h3.entry-title > a")
                title = news.text.strip()
                href = news.get_attribute("href")
                result_item = make_result(
                    SITE_NAME,
                    target,
                    title,
                    href,
                    replace_date(date_text),
                    driver.getIdx(),
                )
                if not limiter.append(result_item):
                    logger.debug(
                        f"🛑 디버그 모드: {target['catCd']} 수집 제한 도달, 중단"
                    )
                    isLoop = False
                    break

            except Exception as e:
                logger.error("❌ 뉴스 row 파싱 실패, HTML:")
                # logger.debug(row.get_attribute("outerHTML"))
                # break
                continue  # 나머지 row는 계속 진행

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
