import json, os, logging
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from transformers import AutoTokenizer, AutoModel
import torch
from collections import defaultdict
from aws.S3Uploader import S3Uploader
from crawler.CrawlingManager import CrawlingManager
from config import settings

logger = logging.getLogger(__name__)


class SummaryClusterer:
    def __init__(
        self,
        driver: CrawlingManager,
        model_name="intfloat/multilingual-e5-base",
        num_clusters=16,
    ):
        self.model_name = model_name
        self.num_clusters = num_clusters
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        self.uuid = driver.uuid
        self.timestamp = driver.timestamp
        self.manager = driver
        self.s3 = S3Uploader()

    def get_embedding(self, text: str):
        input_text = f"passage: {text}"
        inputs = self.tokenizer(
            input_text, return_tensors="pt", truncation=True, max_length=512
        )
        with torch.no_grad():
            outputs = self.model(**inputs)
            return outputs.last_hidden_state[:, 0, :].squeeze().numpy()
        
    def get_batch_embeddings(self, texts: list[str], batch_size=32):
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = [f"passage: {t}" for t in texts[i:i + batch_size]]
            inputs = self.tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
            with torch.no_grad():
                outputs = self.model(**inputs)
                batch_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                embeddings.extend(batch_embeddings)
        return np.array(embeddings)
    
    def load_data(self):
        file_full_path = os.path.join(
            settings.CRAWL_DATA_DIR,
            self.timestamp,
            self.uuid,
            "analyze_result.json",
        )

        return self.s3.loadJsonFromS3(file_full_path)

    def group_by_category(self, data):
        category_map = defaultdict(list)
        for item in data:
            analyze = item.get("analyze")
            if not analyze:
                continue

            summary = analyze.get("summary")
            if not summary:
                continue

            category = analyze.get("category", "기타")
            category_map[category].append((summary, item))
        return category_map



    def cluster_category(self, category, summary_items):
        summaries = [s for s, _ in summary_items]
        if len(summaries) < self.num_clusters:
            logger.info(
                f"⚠️ [{category}] 항목 수 부족 (요약 {len(summaries)}개), 군집 수 {self.num_clusters}보다 작음 → 건너뜀"
            )
            return []

        # embeddings = np.array([self.get_embedding(text) for text in summaries])
        embeddings = self.get_batch_embeddings(summaries)

        kmeans = KMeans(n_clusters=self.num_clusters, random_state=42).fit(embeddings)
        labels = kmeans.labels_

        self.visualize_clusters(embeddings, labels, category)

        clustered_items = []
        for idx, (_, original_item) in enumerate(summary_items):
            original_item["cluster"] = int(labels[idx])
            original_item["cluster_category"] = category
            clustered_items.append(original_item)

        return clustered_items

    def visualize_clusters(self, embeddings, labels, category):
        pca = PCA(n_components=2)
        reduced = pca.fit_transform(embeddings)
        plt.figure(figsize=(10, 7))
        for i in range(self.num_clusters):
            points = reduced[labels == i]
            plt.scatter(points[:, 0], points[:, 1], label=f"Cluster {i}")
        plt.title(f"[{category}] E5 Summary Clustering")
        plt.legend()
        plt.grid(True)
        plt.savefig(f"cluster_plot_{category}.png")
        plt.close()

    def save_results(self, results):
        self.manager.saveResults("clustered", results)

    def run(self):
        raw_data = self.load_data()
        logger.info(f"데이터 로드 완료 : {len(raw_data)}")
        category_map = self.group_by_category(raw_data)
        logger.info(f"그룹핑 완료 : {len(category_map)}")
        all_results = {}

        for category, summary_items in category_map.items():
            logger.info(f"{category} cluster_category 시작")
            logger.info(f"{category} / {len(summary_items)} 시작")
            results = self.cluster_category(category, summary_items)
            all_results[category] = results
            logger.info(f"length : {len(results)}")
            logger.info(f"{category} cluster_category 종료")

        self.save_results(all_results)
        return all_results
