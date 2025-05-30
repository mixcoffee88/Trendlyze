#!/bin/bash
set -e

REPO_DIR="/home/ec2-user/trendlyze/resource/Trendlyze/"
S3_BUCKET="trendlyze-ap-northeast-2-20250526"
S3_PATH="resource/trendlyze.zip"
LOG_FILE="/home/ec2-user/trendlyze/logs/init.log"

# 로그 함수
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

mkdir -p "$(dirname "$LOG_FILE")"

log "🚀 시작"

cd "$REPO_DIR"

# 기존 HEAD 저장
OLD_COMMIT=$(git rev-parse HEAD)

# 최신 코드 pull
git pull origin main >> "$LOG_FILE" 2>&1

# 현재 HEAD 확인
NEW_COMMIT=$(git rev-parse HEAD)

if [ "$OLD_COMMIT" != "$NEW_COMMIT" ]; then
  log "✅ 변경 감지됨: $OLD_COMMIT ➜ $NEW_COMMIT"
  ZIP_FILE="/tmp/project_$(date +'%Y%m%d_%H%M%S').zip"
  zip -r "$ZIP_FILE" . >> "$LOG_FILE" 2>&1

  log "⬆️ S3 업로드 중: $ZIP_FILE ➜ s3://$S3_BUCKET/$S3_PATH"
  aws s3 cp "$ZIP_FILE" "s3://$S3_BUCKET/$S3_PATH" >> "$LOG_FILE" 2>&1

  log "🎉 S3 업로드 성공"
else
  log "📦 Git 최신 상태 유지 중"
fi

exit 0
