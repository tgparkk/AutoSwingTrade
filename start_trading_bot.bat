@echo off
chcp 65001 >nul
echo ====================================
echo   AutoSwingTrade 시작
echo ====================================
echo.

REM 현재 디렉토리를 스크립트 위치로 변경
cd /d "%~dp0"

REM 가상환경 활성화 (만약 있다면)
if exist "venv\Scripts\activate.bat" (
    echo 가상환경 활성화 중...
    call venv\Scripts\activate.bat
    echo 가상환경이 활성화되었습니다.
    echo.
)

REM 필요한 패키지 설치 확인
echo 필요한 패키지 설치 상태 확인 중...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [경고] 일부 패키지 설치에 실패했습니다. 프로그램을 계속 실행합니다...
    echo.
)

REM 설정 파일 확인
if not exist "config\key.ini" (
    echo.
    echo [경고] config\key.ini 파일이 없습니다.
    echo config\key.ini.template 파일을 복사하여 key.ini로 만들고
    echo API 키 정보를 입력해주세요.
    echo.
    pause
    exit /b 1
)

REM 프로그램 시작
echo.
echo AutoSwingTrade 프로그램을 시작합니다...
echo 종료하려면 Ctrl+C를 누르세요.
echo.

python main.py

REM 프로그램 종료 후 메시지
echo.
echo 프로그램이 종료되었습니다.
echo 아무 키나 누르면 창이 닫힙니다.
pause > nul 