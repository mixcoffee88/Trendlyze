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

SITE_NAME = "제일기획 매거진"
URL = "https://magazine.cheil.com/category/{catCd}"
TARGET_LIST = [
    {"catCd": "newsroom/press", "catNm": "보도자료"},
    {"catCd": "newsroom/in-the-media", "catNm": "WorIn the Media"},
    {"catCd": "insight", "catNm": "Insight"},
    {"catCd": "work", "catNm": "Work"},
]


def crawling(driver: CrawlingManager):

    limiter = ResultLimiter()

    for target in TARGET_LIST:
        driver.browser.get(URL.format(catCd=target["catCd"]))
        catCd = target["catCd"]

        isLoop = True
        # ✅ 카테고리별 selector 분기
        if catCd == "newsroom/in-the-media":
            row_selector = "#content > section > div > table > tbody > tr"
            title_selector = "td:nth-child(2) > h5 > a"
            date_selector = "td:nth-child(3) > p"
            wait_selector = "#content > section > div > table > tbody > tr:nth-child(1)"
            total_count_selector = "#content > section > div > div.d-flex.justify-content-between.align-items-center.pb-3.mb-md-2.border-bottom.border-light > div > span"
        else:
            row_selector = "#content > section > div > div.loop-item.media"
            title_selector = "div > div > h6 > a"
            date_selector = "div.media-body > p"
            wait_selector = "#content > section > div > div:nth-child(2)"
            total_count_selector = "#content > section > div > div.d-flex.justify-content-between.align-items-center.mb-md-2 > div > span"

        # 첫번쨰 목록 요소 체크
        WebDriverWait(driver.browser, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
        )

        raw_text = driver.browser.find_element(
            By.CSS_SELECTOR, total_count_selector
        ).text.strip()

        total_count = 0
        # 정규식으로 숫자 추출
        match = re.search(r"\d+", raw_text)
        if match:
            total_count = int(match.group())
            # logger.debug(total_count)  # 예: 116

        while isLoop:
            data_rows = driver.browser.find_elements(By.CSS_SELECTOR, row_selector)
            # logger.debug(len(data_rows))
            last_row = data_rows[-1]

            button_text = driver.browser.find_element(
                By.CSS_SELECTOR, "#fetch-next-page"
            ).text.strip()
            last_row_date_text = last_row.find_element(
                By.CSS_SELECTOR, date_selector
            ).text.strip()
            if (
                not is_within_days(last_row_date_text)
                or len(data_rows) == total_count
                or "마지막" in button_text
            ):
                isLoop = False
                break
            else:

                check_last_title = last_row.find_element(
                    By.CSS_SELECTOR, title_selector
                ).text.strip()

                try:
                    driver.browser.find_element(
                        By.CSS_SELECTOR, "#fetch-next-page"
                    ).click()
                except:
                    isLoop = False
                    break

                for _ in range(20):  # 10초까지 대기
                    new_rows = driver.browser.find_elements(
                        By.CSS_SELECTOR, row_selector
                    )
                    new_last_title = (
                        new_rows[-1]
                        .find_element(By.CSS_SELECTOR, title_selector)
                        .text.strip()
                    )

                    if check_last_title != new_last_title:
                        break
                    time.sleep(0.5)

        rows = driver.browser.find_elements(By.CSS_SELECTOR, row_selector)

        for row in rows:
            try:
                date_text = row.find_element(
                    By.CSS_SELECTOR,
                    date_selector,
                ).text.strip()
                if not is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
                    logger.debug(
                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                    )
                    break

                news = row.find_element(By.CSS_SELECTOR, title_selector)
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
