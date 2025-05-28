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
