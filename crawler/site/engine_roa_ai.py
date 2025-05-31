from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from config import settings

import logging
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.crawling_manager import CrawlingManager
from models.elements import InputField, ActionButton

logger = logging.getLogger(__name__)

SITE_NAME = "Roa"
URL = "https://roa.ai/"
LOGIN_URL = "https://engine.roa.ai/accounts/login?rtnUrl=/discover/news"
NEWS_URL = "https://engine.roa.ai/discover/news?page={pageNum}&limit=50"


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
        id=InputField(attr=By.NAME, attrValue="email", value="jylee@ibank.co.kr"),
        pwd=InputField(
            attr=By.NAME, attrValue="password", value="yjlove83883#", afterEnter=True
        ),
        action=ActionButton(
            # attr=By.CSS_SELECTOR,
            # attrValue="button[type='submit']",
            wait=EC.presence_of_element_located(
                (By.CSS_SELECTOR, "table tr.ant-table-row.ant-table-row-level-0")
            ),
            waitAfterAction=lambda _: on_logout_check(
                driver
            ),  # ✅ 래핑해서 driver 전달
        ),
    )

    if not success:
        logger.error("❌ 로그인 실패로 크롤링 중단")
        return

    pageNum = 0
    isLoop = True

    while isLoop:
        pageNum += 1
        driver.browser.get(NEWS_URL.format(pageNum=pageNum))

        try:
            WebDriverWait(driver.browser, 5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "table tr.ant-table-row.ant-table-row-level-0")
                )
            )
        except Exception as e:
            logger.error(f"❌ {pageNum} 페이지 로드 실패 또는 종료 조건 도달 \n {e}")
            break

        rows = driver.browser.find_elements(
            By.CSS_SELECTOR, "table tr.ant-table-row.ant-table-row-level-0"
        )

        if not rows:
            logger.debug(f"⚠️ 데이터 없음: {pageNum} 페이지")
            break

        logger.debug(f"📄 {pageNum} 페이지: {len(rows)}건 발견")

        for row in rows:
            try:
                a_tag = row.find_element(
                    By.XPATH, "./td/div/div/div/div/div[2]/a[1]"
                )  # 첫 번째 <a> 태그
                title = a_tag.text.strip()
                href = a_tag.get_attribute("href")
                # logger.debug(title)
                # logger.debug(href)
                date_tag = row.find_element(
                    By.XPATH, "./td/div/div/div/div/*[self::div or self::span][last()]"
                )
                date_text = date_tag.text.strip()

                if is_within_days(date_text, day=settings.CRAWLING_LIMIT_DAY):
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
                else:
                    logger.debug(
                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {date_text}"
                    )
                    isLoop = False
                    break  # 날짜가 오래된 첫 뉴스가 나타나면 종료

            except Exception as e:
                logger.error("❌ 뉴스 row 파싱 실패, HTML:")
                # logger.debug(row.get_attribute("outerHTML"))
                # break
                continue  # 나머지 row는 계속 진행

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
