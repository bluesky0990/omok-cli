# CLI Omok Game (오목 게임)

네트워크 기반 CLI 멀티플레이 오목 게임입니다.

## 기능

- 15x15 오목판
- 네트워크 멀티플레이 (서버-클라이언트)
- 방 시스템 (방 생성/목록/입장)
- 화살표 키로 커서 이동
- 실시간 게임 진행
- 5개 연속 승리 조건

## 요구사항

- Python 3.8+
- Windows/Linux/Mac

## 설치

1. 저장소 클론 또는 다운로드

2. 필요한 라이브러리 설치:
```bash
pip install -r requirements.txt
```

## 실행 방법

### 1. 서버 시작

```bash
python server.py
```

서버가 시작되면 다음 메시지가 표시됩니다:
```
Server started on 0.0.0.0:8080
Waiting for connections...
```

### 2. 클라이언트 실행 (2개의 터미널에서)

첫 번째 터미널:
```bash
python client.py
```

두 번째 터미널:
```bash
python client.py
```

### 3. EXE 파일 실행 (빌드된 버전)

`dist` 폴더에 빌드된 클라이언트 실행 파일이 있습니다:

```
dist/
├── omok-client.exe   # 클라이언트 실행 파일
├── config.json       # 설정 파일
└── 실행방법.txt      # 실행 가이드
```

**실행 방법:**
1. `omok-client.exe`를 더블 클릭
2. 또는 명령 프롬프트에서: `omok-client.exe`

**주의:** 화살표 키가 작동하지 않으면 관리자 권한으로 실행하세요.
(exe 파일 우클릭 → 관리자 권한으로 실행)

## 게임 방법

### 1. 연결 및 닉네임 설정
- 클라이언트를 실행하면 자동으로 서버에 연결됩니다
- 닉네임을 입력합니다

### 2. 로비
- **1**: 방 생성 - 방 이름을 입력하여 새 방을 만듭니다
- **2**: 방 입장 - 방 번호를 입력하여 기존 방에 입장합니다
- **3**: 방 목록 새로고침
- **Q**: 종료

### 3. 게임 플레이
- **화살표 키 (↑↓←→)**: 커서 이동
- **Enter**: 현재 커서 위치에 돌 놓기
- **ESC**: 기권 (확인 후 게임 종료)

### 4. 승리 조건
- 가로/세로/대각선으로 정확히 **5개 연속**으로 돌을 놓으면 승리
- 상대방이 기권하면 승리

## 설정

`config.json` 파일에서 다음을 설정할 수 있습니다:

```json
{
  "server": {
    "host": "0.0.0.0",      // 서버 주소
    "port": 8080            // 서버 포트
  },
  "client": {
    "server_address": "localhost",  // 접속할 서버 주소
    "server_port": 8080             // 접속할 서버 포트
  },
  "game": {
    "board_size": 15        // 오목판 크기
  },
  "ui": {
    "black_stone": "●",     // 흑돌 표시
    "white_stone": "○",     // 백돌 표시
    "empty": "·",           // 빈 칸 표시
    "cursor_color": "yellow",  // 커서 색상
    "black_color": "white",    // 흑돌 색상
    "white_color": "cyan"      // 백돌 색상
  }
}
```

## 다른 컴퓨터에서 접속하기

1. 서버를 실행하는 컴퓨터의 IP 주소를 확인합니다

2. 클라이언트 컴퓨터의 `config.json`에서 `server_address`를 서버 IP로 변경:
```json
{
  "client": {
    "server_address": "192.168.1.100",  // 서버 IP 주소로 변경
    "server_port": 8080
  }
}
```

3. 방화벽에서 포트 8080을 허용합니다

## 문제 해결

### keyboard 라이브러리 권한 오류 (Linux)
Linux에서 keyboard 라이브러리는 root 권한이 필요할 수 있습니다:
```bash
sudo python client.py
```

### 서버 연결 실패
- 서버가 실행 중인지 확인
- `config.json`의 주소와 포트 확인
- 방화벽 설정 확인

### 화살표 키가 작동하지 않음
- 관리자 권한으로 실행 (Windows)
- sudo로 실행 (Linux)

## 개발 정보

### 파일 구조
```
omokCLI/
├── server.py          # 서버 프로그램
├── client.py          # 클라이언트 프로그램
├── config.json        # 설정 파일
├── requirements.txt   # 의존성 목록
├── README.md          # 이 파일
├── dist/              # 빌드된 실행 파일
│   ├── omok-client.exe
│   ├── config.json
│   └── 실행방법.txt
└── docs/              # 문서
```

### 기술 스택
- **언어**: Python 3.8+
- **네트워킹**: socket + threading
- **UI**: Rich (터미널 UI)
- **입력**: keyboard (화살표 키)
- **프로토콜**: JSON over TCP
- **빌드**: PyInstaller (exe 변환)

### EXE 빌드 방법

클라이언트를 exe 파일로 빌드하려면:

```bash
# PyInstaller 설치 (이미 설치되어 있으면 생략)
pip install pyinstaller

# 클라이언트 빌드
pyinstaller --onefile --console --name omok-client --add-data "config.json;." client.py
```

빌드된 파일은 `dist/omok-client.exe`에 생성됩니다.

## 향후 추가 기능 (2단계)

- 렌주룰 (3-3, 4-4, 6목 금지)
- 시간 제한 (30초)
- 무르기 요청/응답
- 게임 중 메뉴
- 로깅 시스템

## 라이선스

MIT License

## 기여

버그 리포트나 기능 제안은 이슈로 등록해 주세요!
