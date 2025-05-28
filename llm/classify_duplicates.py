import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from tqdm import tqdm
import json, time, os, platform, re, logging, copy

logger = logging.getLogger(__name__)


# ------- 링크 중복 제거 -------
def deduplicate_by_link(data):
    """
    링크 기준 중복 데이터 제거
    """
    seen = set()
    deduped = []
    for item in data:
        link = item.get("link")
        if link not in seen:
            seen.add(link)
            deduped.append(item)
        else:
            logger.debug(f"중복 : {link}")
    return deduped


def classify_duplicates(
    results,
    threshold: float = 0.85,
    model_name: str = "all-mpnet-base-v2",
):
    """
    속도/효율:
    → all-MiniLM-L6-v2 (추천, 실무 표준) : 모델 크기 및 처리량 TIP(약 80MB),

    정확성:
    → all-mpnet-base-v2 (뉴스, 리포트, 문서, FAQ 등에서 좀 더 높은 품질) : 모델 크기 및 처리량 TIP(약 400MB),

    한국어/다국어:
    → paraphrase-multilingual-MiniLM-L12-v2 또는 jhgan/ko-sbert-sts(한국어 위주) : 모델 크기 및 처리량 TIP(약 120MB),

    최초 사용 시(모델 다운로드)만 인터넷 필요
    이후엔 오프라인 환경에서도 동작

    중복 콘텐츠 분류 함수
    중복 콘텐츠를 대표(R), 중복(D), 고유(N)으로 분류하며,
    중복 항목(D)에는 대표 인덱스(rep_idx)를 추가함.
    대표 항목은 중복 항목의 idx를 duplicates에 포함한다.
    """
    logger.info("중복 콘텐츠 분류를 시작합니다.")
    logger.info(f"사용 모델: {model_name}, 유사도 임계값: {threshold}")
    logger.info(f"총 항목 수: {len(results)}")

    # results = deduplicate_by_link(results)

    logger.info(f"URL 중복 제거후 총 항목 수: {len(results)}")

    texts = [item["content"] for item in results]

    # 텍스트 임베딩
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, show_progress_bar=True)

    # 유사도 계산
    sim_matrix = cosine_similarity(embeddings)

    visited = set()
    output = []

    for i in tqdm(range(len(results)), desc="중복 그룹 분류"):
        if i in visited:
            continue

        # 현재 항목을 대표로 설정
        representative = copy.deepcopy(results[i])
        representative["idx"] = i
        representative["is_duplicate"] = "R"
        representative["duplicates"] = []

        for j in range(i + 1, len(results)):
            if j in visited:
                continue

            if sim_matrix[i][j] > threshold:
                # 중복 항목 처리
                dup = copy.deepcopy(results[j])
                dup["idx"] = j
                dup["is_duplicate"] = "D"
                dup["rep_idx"] = i  # 대표 인덱스 추가

                output.append(dup)

                representative["duplicates"].append(j)
                visited.add(j)

        visited.add(i)

        if not representative["duplicates"]:
            # 중복이 없으면 N 처리
            representative["is_duplicate"] = "N"

        output.append(representative)

    logger.info(f"총 분류된 항목 수: {len(output)}")
    logger.info("중복 콘텐츠 분류가 완료되었습니다.")
    # 결과를 원래 순서대로 정렬
    return sorted(output, key=lambda x: x["idx"])
