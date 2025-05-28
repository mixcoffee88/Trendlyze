from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from config import settings

import json, time, os, platform, logging
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.CrawlingManager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)

SITE_NAME = "Careet"
LOGIN_URL = "https://www.careet.net/User/Login"
NEWS_URL = "https://www.careet.net/NewsClipping?pageidx={pageNum}"


def on_logout_check(driver: webdriver.Chrome):
    # 해당 요소가 존재하고 로드될 때까지 대기 (최대 10초)
    logger.debug("on_logout_check")
    rows = driver.browser.find_elements(
        By.CSS_SELECTOR, "table tr.ant-table-row.ant-table-row-level-0"
    )
    logger.debug(f"on_logout_check : {len(rows)}")
    return len(rows) == 20


def crawling(driver: CrawlingManager):
    limiter = ResultLimiter()
    success = driver.login(
        url=LOGIN_URL,
        id=InputField(attr=By.NAME, attrValue="Email", value="jylee@ibank.co.kr"),
        pwd=InputField(
            attr=By.NAME, attrValue="PCode", value="yjlove83883#", afterEnter=True
        ),
        action=ActionButton(
            attr=By.ID,
            attrValue="btnNext",
            wait=EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.border__item a[href='/User/Logout']")
            ),
        ),
        wait=EC.presence_of_element_located((By.NAME, "Email")),
    )

    if not success:
        email_elements = driver.browser.find_element(
            By.CSS_SELECTOR, "div.border__item a[href='/User/Logout']"
        )
        if not email_elements:
            return

    pageNum = 0
    isLoop = True

    while isLoop:
        pageNum += 1
        driver.browser.get(NEWS_URL.format(pageNum=pageNum))
        time.sleep(0.5)
        try:
            WebDriverWait(driver.browser, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.news-day-item"))
            )
        except Exception as e:
            logger.error(f"❌ {pageNum} 페이지 로드 실패 또는 종료 조건 도달 \n {e}")
            break

        rows = driver.browser.find_elements(By.CSS_SELECTOR, "div.news-day-item")

        if not rows:
            logger.debug(f"⚠️ 데이터 없음: {pageNum} 페이지")
            break

        logger.debug(f"📄 {pageNum} 페이지: {len(rows)}건 발견")

        for row in rows:

            try:
                date_text = row.find_element(
                    By.CSS_SELECTOR, "div.news-item-left span.date"
                ).text.strip()

                if not is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
                    logger.debug(
                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                    )
                    isLoop = False
                    break

                news_lists = row.find_elements(
                    By.CSS_SELECTOR, "div.news-item-right div.accordion-list"
                )

                for news in news_lists:
                    try:

                        title = news.find_element(
                            By.CSS_SELECTOR, "div.accordion-header > p.header-text"
                        ).text.strip()
                        href = news.find_element(
                            By.CSS_SELECTOR, "div.accordion-body a.h-light"
                        ).get_attribute("href")

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
                    except Exception as e:
                        logger.error("❌ 뉴스 row 파싱 실패, HTML:")
                        continue
            except Exception as e:
                logger.error("❌ 뉴스 row 파싱 실패, HTML:")
                continue  # 나머지 row는 계속 진행

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
