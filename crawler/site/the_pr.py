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

SITE_NAME = "THE PR"
URL = "https://www.the-pr.co.kr/news/articleList.html?page={page_num}"


def crawling(driver: CrawlingManager):

    page_num = 0
    isLoop = True
    parsed = urlparse(URL)
    limiter = ResultLimiter()

    while isLoop:
        page_num += 1
        logger.debug(f"page_num : {page_num}")
        driver.browser.get(URL.format(page_num=page_num))

        # 첫번쨰 목록 요소 체크
        WebDriverWait(driver.browser, 10).until(wait_ready_state())

        # 첫페이지 일 경우
        if page_num == 1:
            driver.browser.execute_script(
                f"window.open('{parsed.scheme}://{parsed.netloc}', '_blank');"
            )
            tabs = driver.browser.window_handles

        rows = driver.browser.find_elements(By.CSS_SELECTOR, "#section-list > ul > li")
        for row in rows:
            try:
                start_time = time.time()  # 시작 시간 기록

                driver.browser.switch_to.window(tabs[0])  # 첫번째 탭에서 파싱
                # logger.debug("⚠️ a 태그 . row HTML:", row.get_attribute("outerHTML"))

                href = row.find_element(
                    By.CSS_SELECTOR, "div.view-cont > h2.titles > a"
                ).get_attribute("href")
                time.sleep(0.5)  # 렌더러 준비 기다리기
                driver.browser.switch_to.window(
                    tabs[1]
                )  # 두 번째 탭으로 이동하여 view Url에서 date및 제목 날짜 parsing
                driver.browser.get(href)
                WebDriverWait(driver.browser, 10).until(wait_ready_state())

                date_text = driver.browser.find_element(
                    By.CSS_SELECTOR,
                    "#article-view > div > header > article > div > article:nth-child(1) > ul > li:nth-child(1)",
                ).text.strip()

                if not is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
                    logger.debug(
                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                    )
                    isLoop = False
                    break

                title = driver.browser.find_element(
                    By.CSS_SELECTOR,
                    "#article-view > div > header > article > h1",
                ).text.strip()

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

                driver.browser.switch_to.window(tabs[0])  # 첫번째 탭으로 변환
                time.sleep(0.5)  # 렌더러 준비 기다리기
                elapsed_time = time.time() - start_time  # 경과 시간 계산
                logger.debug(f"⏱️ {href} 소요 시간: {elapsed_time:.2f}초")
            except Exception as e:
                logger.error(f"❌ 오류 발생: {e}")
                continue
    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
