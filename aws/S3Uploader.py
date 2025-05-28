import boto3
import json
import logging
import os
from config import settings

logger = logging.getLogger(__name__)


class S3Uploader:
    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.awes_s3_bucket_name = settings.AWES_S3_BUCKET_NAME

    def saveFileToS3(self, s3_key, results):
        """
        결과 리스트를 S3 버킷의 지정 경로에 JSON 포맷으로 저장
        """
        try:
            s3_key = s3_key.replace("\\", "/")  # S3 키는 항상 '/'로 구분되어야 합니다.
            if not results:
                logger.warning("저장할 결과가 없습니다.")
                return

            json_bytes = json.dumps(results, ensure_ascii=False, indent=2).encode(
                "utf-8"
            )

            self.s3.put_object(
                Bucket=self.awes_s3_bucket_name,
                Key=s3_key,
                Body=json_bytes,
                ContentType="application/json",
            )

            logger.info(f"✅ S3 업로드 완료: s3://{self.awes_s3_bucket_name}/{s3_key}")

        except Exception as e:
            logger.error(
                f"❌ S3 업로드 실패: s3://{self.awes_s3_bucket_name}/{s3_key} → {e}"
            )
            raise

    def loadJsonFromS3(self, s3_key):
        """
        S3에 있는 JSON 파일을 메모리에서 읽어 Python 객체(dict 또는 list)로 반환
        """
        try:
            s3_key = s3_key.replace("\\", "/")  # S3 키는 항상 '/'로 구분되어야 합니다.
            response = self.s3.get_object(Bucket=self.awes_s3_bucket_name, Key=s3_key)
            content = response["Body"].read().decode("utf-8")
            data = json.loads(content)
            logger.info(
                f"📥 메모리 로드 완료: s3://{self.awes_s3_bucket_name}/{s3_key}"
            )
            return data
        except Exception as e:
            logger.error(
                f"❌ S3에서 메모리 로드 실패: s3://{self.awes_s3_bucket_name}/{s3_key} → {e}"
            )
            raise

    def loadAllJsonFromPrefix(self, prefix):
        """
        S3의 특정 prefix에 있는 모든 .json 파일을 메모리에서 읽어 Python 객체로 반환 (list of dict/list)
        """
        loaded_data = []

        try:
            prefix = prefix.replace("\\", "/")  # S3 키는 항상 '/'로 구분되어야 합니다.
            paginator = self.s3.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.awes_s3_bucket_name, Prefix=prefix
            )

            for page in page_iterator:
                for obj in page.get("Contents", []):
                    s3_key = obj["Key"]
                    if s3_key.lower().endswith(".json"):
                        try:
                            response = self.s3.get_object(
                                Bucket=self.awes_s3_bucket_name, Key=s3_key
                            )
                            content = response["Body"].read().decode("utf-8")
                            data = json.loads(content)
                            # --- 여기서 flatten 처리 ---
                            if isinstance(data, list):
                                loaded_data.extend(data)
                            elif isinstance(data, dict):
                                loaded_data.append(data)
                            # dict도 list도 아니면 무시
                            logger.info(f"✅ 로드 완료: {s3_key}")
                        except Exception as inner_e:
                            logger.warning(f"⚠️ JSON 로드 실패: {s3_key} → {inner_e}")
                            continue

            return loaded_data

        except Exception as e:
            logger.error(f"❌ 전체 JSON 메모리 로드 실패 (prefix: {prefix}) → {e}")
            raise
