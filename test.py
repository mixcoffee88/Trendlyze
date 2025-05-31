import json, os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import itertools
from llm.analyze_article import analyze_article

# 1. JSON 파일 읽기
# with open("llm/merge_result.json", "r", encoding="utf-8") as f:
#     data = json.load(f)  # data: list of dict

# test = analyze_article(data)
# print(test)

# # 2. 문서 본문 리스트 추출 (예: "content" 키)
# texts = [item["content"] for item in data]

# # 3. 임베딩 모델 로드 및 임베딩 생성
# model = SentenceTransformer("all-mpnet-base-v2")
# embeddings = model.encode(texts, show_progress_bar=True)

# # 4. 유사도 행렬 계산
# sim_matrix = cosine_similarity(embeddings)

# # 5. 쌍별 유사도 분석 (예: threshold=0.85)
# threshold = 0.85
# similar_pairs = []
# for i, j in itertools.combinations(range(len(texts)), 2):
#     print(f"비교 중: {i} <-> {j} (유사도={sim_matrix[i][j]:.4f})")
#     if sim_matrix[i][j] > threshold:
#         similar_pairs.append((i, j, sim_matrix[i][j]))

# # 6. 결과 출력 (혹은 json/csv 등으로 저장)
# print(f"유사도 {threshold} 이상 쌍: {len(similar_pairs)}개")
# for i, j, sim in similar_pairs[:20]:
#     print(f"idx {i} <-> idx {j} (유사도={sim:.4f})")
#     # print("문서1:", texts[i][:100])
#     # print("문서2:", texts[j][:100])

print(
    os.path.join(
        "tem/aaa",
        "20240505",
        "",
        f"test_result.json",
    )
)
