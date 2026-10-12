# Window Position

Windows에서 앱 창의 위치와 크기를 슬롯에 저장하고 `Alt+1`부터 `Alt+0`까지 전역 단축키로 복원하는 작은 Python 프로그램입니다.

## 사용 방법

1. Python 3.10 이상을 설치합니다.
2. 프로젝트 폴더에서 의존성을 설치합니다.

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. `py main.py`를 실행합니다.
4. Window Position에서 원하는 슬롯의 `저장` 버튼을 누릅니다.
5. 저장 대기 메시지가 나타나면 60초 안에 저장할 프로그램 창을 직접 클릭합니다. 선택한 창이 0.5초간 활성 상태를 유지하면 현재 위치와 크기가 자동 저장됩니다.
6. 이후 어느 앱을 사용 중이든 `Alt+1`~`Alt+9`, `Alt+0`을 누르면 저장한 창을 원래 위치와 크기로 복원합니다.
7. 오른쪽 위 `X` 또는 `프로그램 종료`를 누르면 프로그램이 완전히 종료됩니다.

저장 데이터는 `%APPDATA%\WindowPosition\slots.json`에 기록됩니다. 앱을 다시 실행해도 슬롯이 유지됩니다.

## 실행 파일 만들기

```powershell
python -m pip install pyinstaller
pyinstaller --noconsole --onefile --name WindowPosition --icon icon.ico --add-data "icon.ico;." main.py
```

실행 파일은 `dist\WindowPosition.exe`에 생성됩니다.

## 알려진 제한

- Windows 전용입니다.
- 관리자 권한으로 실행 중인 앱은 Window Position도 관리자 권한으로 실행해야 위치를 변경할 수 있습니다.
- 같은 실행 파일로 열린 창이 여러 개이면 제목과 창 종류를 기준으로 가장 가까운 창을 선택합니다.
- 다른 프로그램이 이미 `Alt+숫자` 단축키를 사용 중이면 해당 슬롯 단축키가 등록되지 않을 수 있습니다.

## 공개 배포

이 저장소를 `mainyh` 계정의 GitHub 저장소로 공개하려면 새 public repository를 만든 뒤 다음을 실행합니다.

```powershell
git init
git add .
git commit -m "Initial Window Position app"
git branch -M main
git remote add origin https://github.com/mainyh/window-position.git
git push -u origin main
```

저장소 이름은 원하는 이름으로 바꿀 수 있습니다.
