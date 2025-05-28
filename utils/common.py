from datetime import datetime
import re, logging

logger = logging.getLogger(__name__)


def is_within_days(date_text: str, date_format: str = None, day: int = 30) -> bool:
    try:
        replace_date_text = replace_date(date_text, date_format).replace(".", "")
        # 특수문자 및 공백 제거
        cleaned = replace_date_text[:8]

        # 문자열이 8자리인지 확인
        if len(cleaned) != 8:
            logger.error(f"❌ 날짜 형식 오류: '{date_text}' → '{cleaned}' (8자리 아님)")
            return False

        # 날짜 변환
        parsed_date = datetime.strptime(cleaned, "%Y%m%d")

        # 오늘 날짜 기준 비교
        return 0 <= (datetime.today() - parsed_date).days <= day

    except ValueError as e:
        logger.error(f"❌ 날짜 파싱 오류: '{date_text}' → {e}")
        return False


def replace_date(date_text: str, date_format: str = None) -> str:
    try:
        # 한글 제거 및 앞뒤 공백 제거
        clean_text = re.sub(r"[가-힣]+", "", date_text).strip()

        if date_format:
            dt = datetime.strptime(clean_text, date_format)
        else:
            # 숫자만 추출
            digits = re.sub(r"[^\d]", "", clean_text)[:8]
            if len(digits) != 8:
                logger.warning(
                    f"⚠️ 잘못된 날짜 문자열 (8자리 아님): '{date_text}' → '{digits}'"
                )
                return ""
            dt = datetime.strptime(digits, "%Y%m%d")

        return dt.strftime("%Y.%m.%d")

    except ValueError as e:
        logger.error(
            f"❌ replace_date 변환 실패: '{date_text}' with format '{date_format}' → {e}"
        )
        return ""


def make_result(name, target, title, href, date_text, idx=None):
    # target이 None이면 빈 dict로 대체
    meta = {"origin": name}
    if target:
        meta.update(target)
    return {
        "idx": idx,
        "metaData": meta,
        "title": title,
        "link": href,
        "date": date_text,
    }


def wait_ready_state():
    def _ready(d):
        try:
            state = d.execute_script("return document.readyState")
            logger.debug(f"📄 readyState: {state}")
            return state == "complete"
        except Exception as e:
            logger.error(f"readyState 확인 중 오류: {e}")
            return False

    return _ready
