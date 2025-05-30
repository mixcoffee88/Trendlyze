#!/bin/bash
set -e

ROOT_DIR="/home/ec2-user/trendlyze"
REPO_DIR="$ROOT_DIR/resource/Trendlyze"
TMP_DIR="$ROOT_DIR/tmp"
S3_BUCKET="trendlyze-ap-northeast-2-20250526"
S3_PATH="resource/trendlyze.zip"
SCRIPT_S3_KEY="scripts/node_start.sh"
LOG_DATE=$(date '+%Y-%m-%d')
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/log_${LOG_DATE}.log"
LOCK_FILE="$ROOT_DIR/hub_start.lock"

REGION="ap-northeast-2"
TAG_KEY="crawler-type"
TAG_VALUE="node"
COMMAND="$ROOT_DIR/node_start.sh"

# 최신 스크립트 경로
HUB_SCRIPT_LOCAL_PATH="$REPO_DIR/scripts/hub_start.sh"
HUB_TARGET_SCRIPT="$ROOT_DIR/hub_start.sh"
NODE_SCRIPT_LOCAL_PATH="$REPO_DIR/scripts/node_start.sh"
NODE_SCRIPT_TMP_LOCAL_PATH="$TMP_DIR/node_start_tmp.sh"
NODE_TARGET_SCRIPT=$COMMAND

# Lambda 함수 이름 지정
LAMBDA_FUNCTION_NAME="trendlyze-instance-start"

mkdir -p "$TMP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# 로그 함수
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# 락 파일 처리
if [ -f "$LOCK_FILE" ]; then
  log "🚫 다른 실행 중. 종료"
  exit 1
fi
touch "$LOCK_FILE"

# 종료 시 명령 실행 결과 출력
print_final_status() {
  if [[ -n "$CMD_ID" ]]; then
    log "📋 종료 시점 상태 출력 중..."
    aws ssm list-command-invocations \
      --command-id "$CMD_ID" \
      --region "$REGION" \
      --details \
      --query "CommandInvocations[*].{Instance:InstanceId,Status:Status,Output:CommandPlugins[0].Output}" \
      --output table
  else
    log "📋 종료 시점에 Command ID 없음 - 상태 출력 생략"
  fi
}

on_exit() {
  print_final_status
  rm -f "$LOCK_FILE"
}
trap on_exit EXIT
trap 'echo "💥 예기치 않은 오류 발생!" >> "$LOG_FILE"; rm -f "$LOCK_FILE"' ERR

log "🚀 시작(v0.0.1)"

cd "$REPO_DIR"

# jq 설치 확인 및 자동 설치
if ! command -v jq >/dev/null 2>&1; then
  log "📦 jq 미설치 상태 - 설치 시도 중..."
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
      amzn)
        sudo yum install -y jq >> "$LOG_FILE" 2>&1 && log "✅ jq 설치 완료 (Amazon Linux)" || log "❌ jq 설치 실패"
        ;;
      ubuntu)
        sudo apt-get update >> "$LOG_FILE" 2>&1
        sudo apt-get install -y jq >> "$LOG_FILE" 2>&1 && log "✅ jq 설치 완료 (Ubuntu)" || log "❌ jq 설치 실패"
        ;;
      *)
        log "⚠️ 지원되지 않는 OS: $ID. jq 수동 설치 필요"
        ;;
    esac
  else
    log "⚠️ OS 정보를 확인할 수 없습니다. jq 설치 수동 진행 요망"
  fi
else
  log "🧩 jq 설치 확인 완료"
fi

# git 변경 감지 후 zip 및 S3 업로드
OLD_COMMIT=$(git rev-parse HEAD)
git pull origin main >> "$LOG_FILE" 2>&1
NEW_COMMIT=$(git rev-parse HEAD)

if [ "$OLD_COMMIT" != "$NEW_COMMIT" ]; then
  log "✅ 변경 감지됨: $OLD_COMMIT ➜ $NEW_COMMIT"
  ZIP_FILE="$TMP_DIR/project_$(date +'%Y%m%d_%H%M%S').zip"
  zip -r "$ZIP_FILE" . -x "*.git*" "*.venv*" "*__pycache__*" "*.log" "*.DS_Store" "*.bak" "*.tmp" >> "$LOG_FILE" 2>&1

  log "⬆️ S3 업로드 중: $ZIP_FILE ➜ s3://$S3_BUCKET/$S3_PATH"
  if ! aws s3 cp "$ZIP_FILE" "s3://$S3_BUCKET/$S3_PATH" --region "$REGION" >> "$LOG_FILE" 2>&1; then
    log "❌ S3 업로드 실패. 중단합니다."
    rm -f "$ZIP_FILE"
    exit 1
  fi
  log "🎉 S3 업로드 성공"
else
  log "📦 Git 최신 상태 유지 중"
fi

# 노드 스크립트 존재 여부 확인
if [ ! -r "$NODE_SCRIPT_LOCAL_PATH" ]; then
  log "❌ $NODE_SCRIPT_LOCAL_PATH 읽기 불가. 중단합니다."
  exit 1
fi

# 허브 스크립트 존재 여부 확인
if [ ! -r "$HUB_SCRIPT_LOCAL_PATH" ]; then
  log "❌ $HUB_SCRIPT_LOCAL_PATH 읽기 불가. 중단합니다."
  exit 1
fi

# 현재 hub_start.sh와 최신본이 다르면 업데이트 후 재실행
CURRENT_HASH=$(sha256sum "$HUB_TARGET_SCRIPT" 2>/dev/null | awk '{print $1}')
LATEST_HASH=$(sha256sum "$HUB_SCRIPT_LOCAL_PATH" | awk '{print $1}')

if [[ "$CURRENT_HASH" != "$LATEST_HASH" ]]; then
  log "♻️ hub_start.sh 변경 감지됨. 최신본으로 덮어쓰기 후 Lambda 재호출 요청"
  echo "♻️ hub_start.sh 변경 감지됨. 최신본으로 덮어쓰기 후 Lambda 재호출 요청"
  cp "$HUB_SCRIPT_LOCAL_PATH" "$HUB_TARGET_SCRIPT"
  chmod +x "$HUB_TARGET_SCRIPT"

  
  log "🚀 Lambda 재호출 요청 완료 → 함수명: $LAMBDA_FUNCTION_NAME"
  # Lambda 재호출
  if ! aws lambda invoke \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --invocation-type Event \
    --cli-binary-format raw-in-base64-out \
    --payload '{"body": "{\"command\": \"retry\"}"}' \
    $LOG_DIR/lambda_output.json; then
    log "❌ Lambda 호출 실패. 스크립트 중단"
    exit 1
  fi
  log "🛑 현재 hub_start.sh 종료"
  exit 0
fi

# 인스턴스 조회 및 시작
INSTANCE_IDS=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:$TAG_KEY,Values=$TAG_VALUE" "Name=instance-state-name,Values=stopped,running" \
  --query "Reservations[*].Instances[*].InstanceId" \
  --output text)

if [[ -z "$INSTANCE_IDS" || "$INSTANCE_IDS" == "None" ]]; then
  log "⚠️ 실행할 인스턴스 없음. 종료"
  exit 1
else
  log "▶️ 인스턴스 시작 중: $INSTANCE_IDS"
  aws ec2 start-instances --region "$REGION" --instance-ids $INSTANCE_IDS >> "$LOG_FILE" 2>&1
  log "⏳ 인스턴스 상태 대기 중..."
  aws ec2 wait instance-running --region "$REGION" --instance-ids $INSTANCE_IDS
  log "✅ 인스턴스 실행 완료"
fi

# SSM Agent 활성화 확인
log "🕐 SSM 에이전트 준비 상태 확인 시작..."
for i in {1..40}; do
  ALL_READY=true
  for INSTANCE_ID in $INSTANCE_IDS; do
    SSM_STATUS=$(aws ssm describe-instance-information \
      --region "$REGION" \
      --query "InstanceInformationList[?InstanceId=='$INSTANCE_ID'].PingStatus" \
      --output text)
    if [[ "$SSM_STATUS" != "Online" ]]; then
      log "⏳ [$INSTANCE_ID] SSM 상태: $SSM_STATUS - 대기 중..."
      ALL_READY=false
    else
      log "✅ [$INSTANCE_ID] SSM 상태: Online"
    fi
  done
  if $ALL_READY; then
    log "✅ 모든 인스턴스의 SSM 에이전트 활성화 확인 완료"
    break
  fi
  if [[ "$i" -eq 20 ]]; then
    log "❌ SSM 에이전트가 활성화되지 않은 인스턴스가 있습니다. 중단합니다."
    exit 1
  fi
  sleep 5
done

# 최신 스크립트 비교 및 S3 업로드
TMP_HASH=$(sha256sum "$NODE_SCRIPT_LOCAL_PATH" | awk '{print $1}')
if aws s3 cp "s3://$S3_BUCKET/$SCRIPT_S3_KEY" "$NODE_SCRIPT_TMP_LOCAL_PATH" 2>/dev/null; then
  EXISTING_HASH=$(sha256sum "$NODE_SCRIPT_TMP_LOCAL_PATH" | awk '{print $1}')
  rm -f "$NODE_SCRIPT_TMP_LOCAL_PATH"
else
  EXISTING_HASH=""
fi

# 특정 인스턴스가 이전 오류로 sh파일이 최신화가 아닐가능성이있어서 분기제거
log "⬆️ S3에 최신 node_start.sh 업로드 중..."
aws s3 cp "$NODE_SCRIPT_LOCAL_PATH" "s3://$S3_BUCKET/$SCRIPT_S3_KEY" --region "$REGION"
log "✅ 업로드 완료"
log "🚀 노드 스크립트 최신화 시작"
SCRIPT_CMD_ID=$(aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --targets "Key=tag:$TAG_KEY,Values=$TAG_VALUE" \
  --parameters "commands=[ 'aws s3 cp s3://$S3_BUCKET/$SCRIPT_S3_KEY $NODE_TARGET_SCRIPT', 'chmod +x $NODE_TARGET_SCRIPT' ]" \
  --comment "노드 최신화 실행" \
  --region "$REGION" \
  --query "Command.CommandId" \
  --output text)
log "⏳ 실행 결과 확인 중... (CommandId: $SCRIPT_CMD_ID)"
sleep 5
aws ssm list-command-invocations \
  --command-id "$SCRIPT_CMD_ID" \
  --region "$REGION" \
  --details \
  --query "CommandInvocations[*].{Instance:InstanceId,Status:Status,Output:CommandPlugins[0].Output}" \
  --output table
log "✅ 최신화 완료"

# 💬 SSM 명령 전송(node instance의 node_start.sh 실행)
log "📤 SSM 명령 전송 중..."
CMD_ID=$(aws ssm send-command \
  --document-name "AWS-RunShellScript" \
  --targets "Key=tag:$TAG_KEY,Values=$TAG_VALUE" \
  --parameters "commands=['$COMMAND']" \
  --comment "자동 실행" \
  --region "$REGION" \
  --query "Command.CommandId" \
  --output text)

log "⏳ 실행 결과 확인 중... (CommandId: $CMD_ID)"
sleep 5

# 상태가 Success 될 때까지 폴링 (예: 5초 간격 100회)
for i in {1..100}; do
  log "⏳ 상태 확인 중 ($i)..."
  INVOCATIONS=$(aws ssm list-command-invocations \
    --command-id "$CMD_ID" \
    --region "$REGION" \
    --details \
    --query "CommandInvocations[*].{Instance:InstanceId,Status:Status}" \
    --output json)
  TOTAL=$(echo "$INVOCATIONS" | jq length)
  SUCCESS_COUNT=$(echo "$INVOCATIONS" | jq '[.[] | select(.Status=="Success")] | length')
  FAILED_COUNT=$(echo "$INVOCATIONS" | jq '[.[] | select(.Status=="Failed")] | length')
  PENDING_COUNT=$(echo "$INVOCATIONS" | jq '[.[] | select(.Status=="Pending" or .Status=="InProgress")] | length')
  log "🧭 상태: 총 $TOTAL개 중 성공 $SUCCESS_COUNT개 / 실패 $FAILED_COUNT개 / 대기중 $PENDING_COUNT개"
  if [[ "$SUCCESS_COUNT" -eq "$TOTAL" ]]; then
    log "✅ 모든 인스턴스 스크립트 실행 완료"
    break
  fi
  if [[ "$FAILED_COUNT" -gt 0 ]]; then
    log "❌ 일부 인스턴스 스크립트 실패"
    FAILED_INSTANCES=$(echo "$INVOCATIONS" | jq -r '.[] | select(.Status=="Failed") | .Instance')
    log "❌ 실패한 인스턴스 목록: $FAILED_INSTANCES"
    break
  fi
  sleep 5
done


FAILED_COUNT=${FAILED_COUNT:-0}
TOTAL=${TOTAL:-0}
if [[ "$TOTAL" -gt 0 && "$FAILED_COUNT" -eq "$TOTAL" ]]; then
  log "❌ 모든 스크립트 동작실패"
  log "▶️ 인스턴스 강제 종료 중: $INSTANCE_IDS"
  aws ec2 stop-instances --region "$REGION" --instance-ids $INSTANCE_IDS >> "$LOG_FILE" 2>&1
  log "⏳ 인스턴스 상태 대기 중..."
  aws ec2 wait instance-stopped --region "$REGION" --instance-ids $INSTANCE_IDS
  log "✅ 인스턴스 종료 완료"
  exit 1
fi

[[ -f "$ZIP_FILE" ]] && rm -f "$ZIP_FILE"

# 📁 오래된 로그 정리 (30일 초과)
log "🧹 30일 초과 로그 정리 시작"
find "$ROOT_DIR/logs" -type f -name "log_*.log" -mtime +30 -print -delete >> "$LOG_FILE" 2>&1
log "🧼 로그 정리 완료"

log "🏁 hub_start.sh 정상 종료됨"


exit 0

