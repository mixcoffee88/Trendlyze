#!/bin/bash
set -e
export TMPDIR=/home/ec2-user/tmp

# ==== 설정 ====
APP_NAME="trendlyze"
ROOT_DIR="/home/ec2-user/trendlyze"
RESOURCE_DIR="$ROOT_DIR/resource"
TEMP_DIR="$ROOT_DIR/tmp"
LOG_DATE=$(date '+%Y-%m-%d')
LOG_FILE="$ROOT_DIR/logs/log_${LOG_DATE}.log"

S3_BUCKET="trendlyze-ap-northeast-2-20250526"
S3_KEY="resource/trendlyze.zip"

EFS_ID="fs-0240109ff0de502f9"
EFS_DIR="/mnt/efs"
EFS_HOST="${EFS_ID}.efs.ap-northeast-2.amazonaws.com"

ZIP_FILENAME="${APP_NAME}.zip"
ZIP_FILE="$RESOURCE_DIR/$ZIP_FILENAME"
TEMP_ZIP_FILE="$TEMP_DIR/$ZIP_FILENAME"
PROJECT_DIR="$RESOURCE_DIR/$APP_NAME"
ETAG_FILE="$ZIP_FILE.etag"

# ==== Chrome 및 Chromedriver S3 다운로드 및 압축 해제 ====
DRIVER_DIR="$RESOURCE_DIR/driver"
# chrome.zip
CHROME_ZIP_KEY="resource/driver/linux/chrome.zip"
CHROME_ZIP_FILE="$TEMP_DIR/chrome.zip"
# chromedriver.zip
CHROMEDRIVER_ZIP_KEY="resource/driver/linux/chromedriver.zip"
CHROMEDRIVER_ZIP_FILE="$TEMP_DIR/chromedriver.zip"

mkdir -p "$DRIVER_DIR"
mkdir -p "$TEMP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$RESOURCE_DIR"
mkdir -p $TMPDIR

# ==== 공통 함수 ====
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

save_etag() {
  echo "$REMOTE_ETAG" > "$ETAG_FILE"
}

is_zip_changed() {
  [[ ! -f "$ZIP_FILE" ]] && return 0
  local temp_hash=$(sha256sum "$TEMP_ZIP_FILE" | awk '{print $1}')
  local local_hash=$(sha256sum "$ZIP_FILE" | awk '{print $1}')
  [[ "$temp_hash" != "$local_hash" ]]
}

download_and_extract() {
  log "⬇️ S3에서 ZIP 파일 다운로드 중..."
  aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "$TEMP_ZIP_FILE" >> "$LOG_FILE" 2>&1

  if is_zip_changed; then
    log "⚠️ 파일 변경 감지됨. 기존 파일 및 디렉토리 제거 중..."
    rm -f "$ZIP_FILE"
    [ -d "$PROJECT_DIR" ] && rm -rf "$PROJECT_DIR"/*
  else
    log "✅ 동일한 파일입니다. 변경 없음."
    rm -f "$TEMP_ZIP_FILE"
    return
  fi

  mv "$TEMP_ZIP_FILE" "$ZIP_FILE"
  log "📦 ZIP 파일 압축 해제 중..."
  unzip -o "$ZIP_FILE" -d "$PROJECT_DIR" >> "$LOG_FILE" 2>&1
  save_etag
}

# ==== 준비 ====
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$TEMP_DIR"
sudo mkdir -p "$EFS_DIR"

log "🚀 시작"

# ==== EFS 마운트 ====
if ! findmnt -rn -S "$EFS_HOST:/" -T "$EFS_DIR" > /dev/null; then
  log "🔗 EFS 마운트 중: $EFS_ID ➜ $EFS_DIR"
  sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport \
    "${EFS_HOST}":/ "$EFS_DIR" >> "$LOG_FILE" 2>&1 || {
    log "❌ EFS 마운트 실패"
    exit 1
  }
else
  log "✅ EFS 이미 마운트됨"
fi

# ==== ETag 비교 및 처리 ====
REMOTE_ETAG=$(aws s3api head-object \
  --bucket "$S3_BUCKET" \
  --key "$S3_KEY" \
  --query ETag --output text | tr -d '"')

if [[ -f "$ETAG_FILE" ]]; then
  LOCAL_ETAG=$(cat "$ETAG_FILE")
  if [[ "$REMOTE_ETAG" == "$LOCAL_ETAG" ]]; then
    log "✅ 동일한 ETag 감지됨. 다운로드 생략"
  else
    log "📁 변경된 ETag 감지됨. 다운로드 수행"
    download_and_extract
  fi
else
  log "📁 ETag 없음. 새로 다운로드"
  download_and_extract
fi

# Python 3.11.9 설치 여부 확인
PYTHON_VERSION=$(python3.11 --version 2>/dev/null || echo "not_installed")

if [[ "$PYTHON_VERSION" == "Python 3.11.9" ]]; then
    log "✅ Python 3.11.9 is already installed."
else
    log "📦 Installing Python 3.11.9..."

    # 의존 패키지 설치
    log yum update -y
    sudo yum update -y >> "$LOG_FILE" 2>&1
    log yum groupinstall "Development Tools" -y
    sudo yum groupinstall "Development Tools" -y >> "$LOG_FILE" 2>&1
    log yum install gcc openssl-devel bzip2-devel libffi-devel wget -y
    sudo yum install gcc openssl-devel bzip2-devel libffi-devel wget -y >> "$LOG_FILE" 2>&1


    # 소스 다운로드 및 설치
    cd /usr/src
    sudo wget https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
    sudo tar xzf Python-3.11.9.tgz
    cd Python-3.11.9
    sudo ./configure --enable-optimizations
    sudo make altinstall || { log "❌ Python build 실패"; exit 1; }

    log "✅ Python 3.11.9 installed successfully."
fi

# requirements.txt 설치
log "📦 Installing requirements.txt modules..."
cd "$PROJECT_DIR"
python3.11 -m venv $ROOT_DIR/.venv
source $ROOT_DIR/.venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt >> "$LOG_FILE" 2>> "$LOG_FILE" || { log "❌ requirements 설치 실패"; exit 1; }

log "✅ All required modules installed."

# --- Chrome ---
CHROME_EXEC="$DRIVER_DIR/chrome/chrome"
if [[ ! -f "$CHROME_EXEC" ]]; then
  log "🕵️ chrome 실행파일 없음 ➜ S3에서 다운로드"
  CHROME_ZIP_KEY="resource/driver/linux/chrome.zip"
  CHROME_ZIP_FILE="$TEMP_DIR/chrome.zip"

  log "⬇️ S3에서 chrome.zip 다운로드 중..."
  aws s3 cp "s3://${S3_BUCKET}/${CHROME_ZIP_KEY}" "$CHROME_ZIP_FILE" >> "$LOG_FILE" 2>&1 || { log "❌ chrome.zip 다운로드 실패"; exit 1; }

  log "📦 chrome.zip 압축 해제 중..."
  mkdir -p "$DRIVER_DIR/chrome"
  unzip -o "$CHROME_ZIP_FILE" -d "$DRIVER_DIR/chrome" >> "$LOG_FILE" 2>&1
  rm -f "$CHROME_ZIP_FILE"
else
  log "✅ chrome 실행파일 존재함 ➜ 다운로드 생략"
fi

# --- Chromedriver ---
CHROMEDRIVER_EXEC="$DRIVER_DIR/chromedriver/chromedriver"
if [[ ! -f "$CHROMEDRIVER_EXEC" ]]; then
  log "🕵️ chromedriver 실행파일 없음 ➜ S3에서 다운로드"
  CHROMEDRIVER_ZIP_KEY="resource/driver/linux/chromedriver.zip"
  CHROMEDRIVER_ZIP_FILE="$TEMP_DIR/chromedriver.zip"

  log "⬇️ S3에서 chromedriver.zip 다운로드 중..."
  aws s3 cp "s3://${S3_BUCKET}/${CHROMEDRIVER_ZIP_KEY}" "$CHROMEDRIVER_ZIP_FILE" >> "$LOG_FILE" 2>&1 || { log "❌ chromedriver.zip 다운로드 실패"; exit 1; }

  log "📦 chromedriver.zip 압축 해제 중..."
  mkdir -p "$DRIVER_DIR/chromedriver"
  unzip -o "$CHROMEDRIVER_ZIP_FILE" -d "$DRIVER_DIR/chromedriver" >> "$LOG_FILE" 2>&1
  rm -f "$CHROMEDRIVER_ZIP_FILE"
else
  log "✅ chromedriver 실행파일 존재함 ➜ 다운로드 생략"
fi

chmod +x "$CHROME_EXEC"
chmod +x "$CHROMEDRIVER_EXEC"

log "🎉 배포 완료"
exit 0
