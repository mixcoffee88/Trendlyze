from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

import json, time, os, platform, logging
from config import settings
from utils.result_limiter import ResultLimiter
from utils.common import is_within_days, replace_date, make_result, wait_ready_state
from crawler.crawling_manager import CrawlingManager
from models.elements import InputField, ActionButton
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SITE_NAME = "OpenAds"
URL = "https://www.openads.co.kr/home"
LIMIT = 9
TARGET_LIST = [
    {"catCd": "CC49", "catNm": "트랜드"},
    {"catCd": "CC92", "catNm": "비지니스"},
    {"catCd": "CC58", "catNm": "마케팅 전략"},
    {"catCd": "CC68", "catNm": "디지털 광고"},
    {"catCd": "CC107", "catNm": "데이터"},
    {"catCd": "CC97", "catNm": "리포트자료실"},
    {"catCd": "CC82", "catNm": "커리어"},
    {"catCd": "CC75", "catNm": "업무스킬"},
    {"catCd": "CC86", "catNm": "자기개발"},
    {"catCd": "CC114", "catNm": "오드리책방"},
    {"catCd": "CC121", "catNm": "오스토리"},
]

DATA_CALL_SCRIPT = """
    const formData = new FormData();
    formData.append('categoryCode', '{categoryCode}');
    formData.append('subCategoryCode', '');
    formData.append('offset', {offset});
    formData.append('limit', {limit});

    fetch('https://www.openads.co.kr/content/cardContent', {{
        method: 'POST',
        body: formData,
        credentials: 'include'  // 쿠키 등 인증 유지 시 필요
    }}).then(response => response.text())
    .then(result => {{
        console.log("✅ 로그인 결과:", result);
        window.contentResult = result;
    }}).catch(err => {{
        console.error("❌ 에러:", err);
        window.contentResult = "ERROR";
    }});
"""


def crawling(driver: CrawlingManager):
    driver.browser.get(URL)
    WebDriverWait(driver.browser, 5).until(lambda d: "오픈애즈" in d.title)
    limiter = ResultLimiter()

    for target in TARGET_LIST:
        logger.debug(f"{target['catNm']} 진행 시작")
        is_loop = True
        page_num = 0
        while is_loop:
            # 트렌드 기본값 CC49, 9개
            offset = page_num * LIMIT
            page_num += 1
            time.sleep(0.5)  # 서버에서 막힐수도 있으니깐 호출전에 잠깐
            driver.browser.execute_script(
                DATA_CALL_SCRIPT.format(
                    categoryCode=target["catCd"], offset=offset, limit=LIMIT
                )
            )
            logger.debug(f"{target['catNm']} / {offset} 호출 진행")

            result = None
            for _ in range(20):  # 10초까지 대기
                result = driver.browser.execute_script("return window.contentResult")
                if result:
                    break
                time.sleep(0.5)

            if result and result != "ERROR":
                try:
                    json_data = json.loads(result)
                    if json_data.get("success", False):
                        message = json_data.get("message", {})
                        cards = message.get("cards", [])
                        total_count = message.get("totalContsCnt", 0)

                        if offset >= total_count:
                            logger.debug(
                                f"✅ 종료 조건 도달: offset {offset} ≥ total {total_count}"
                            )
                            is_loop = False
                            break

                        for j in cards:
                            try:
                                pub_date = j.get("pubDtime", "")
                                if is_within_days(
                                    pub_date, day=settings.CRAWLING_LIMIT_DAY
                                ):
                                    result_item = make_result(
                                        SITE_NAME,
                                        target,
                                        j.get("title"),
                                        f'https://www.openads.co.kr/content/contentDetail?contsId={j["contsId"]}',
                                        replace_date(pub_date),
                                        driver.getIdx(),
                                    )
                                    if not limiter.append(result_item):
                                        logger.debug(
                                            f"🛑 디버그 모드: {target['catCd']} 수집 제한 도달, 중단"
                                        )
                                        is_loop = False
                                        break
                                else:
                                    logger.debug(
                                        f"⏩ 무시 ({settings.CRAWLING_LIMIT_DAY}일 초과): {pub_date}"
                                    )
                                    is_loop = False
                                    break
                            except Exception as e:
                                logger.error(f"❌ 카드 처리 오류: {e}")
                                continue
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON 파싱 실패: {e}")
                    is_loop = False
                    break
            else:
                logger.error("❌ 유효하지 않은 결과:", result)
                is_loop = False
                break
        logger.debug(f"{target['catNm']} 진행 종료")

    driver.closeExtraTabs()
    limiter.results = driver.crawing_content(limiter.results)
    driver.saveResults(SITE_NAME, limiter.results)
