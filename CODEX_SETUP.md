# ARTICLE AI — 다른 Windows PC에서 Codex로 설치하기

이 파일은 Codex가 읽고 실제 설치 스크립트를 실행하기 위한 지시문입니다. 이 파일 자체는 설치 프로그램이 아닙니다. 사용자는 다음 문구로 시작할 수 있습니다.

> 이 저장소의 CODEX_SETUP.md를 읽고, 다른 프로그램과 기존 데이터를 보호하면서 이 PC에 ARTICLE AI를 설치하고 가능한 기능을 검증해 줘. 필요한 모델 다운로드 전에 용량과 조건을 알려줘.

## 먼저 알릴 사실

- 이 저장소는 **공개 배포 후보**이며, 기존 개발 PC와 완전히 같은 제품을 재현하는 상태가 아닙니다. 현재 구현과 미구현 항목은 `docs/ko/ARCHITECTURE.md`에 있습니다.
- PDF 220개, 기존 원문·DB·색인과 사용자 원고는 저장소에 없습니다. 새 설치의 문헌은 0건입니다. 사용자가 사용 권한이 있는 PDF를 다시 등록해야 하며, 등록 문헌·모델·설정이 다르면 검색과 분석 결과도 달라집니다.
- 현재 이 저장소의 문자 검색·문자 일치 검사·보고서·개념 사전과 실험 CPU 임베딩·리랭킹을 대상으로 합니다. GPT-OSS 응답, 원본 PostgreSQL/OpenSearch와 Hybrid 검색, OCR, GPU 자동 적응, 원본 제품의 전체 기능은 복구되지 않습니다.
- 실제로 검증하지 않은 하드웨어나 모델, 새 PC 설치를 PASS로 보고하지 않습니다. 이 저장소의 코드는 Apache-2.0이며 PDF와 모델에는 별도의 권리가 적용됩니다.

## Codex 실행 계약

1. 사용자가 선택한 새 설치 폴더를 확인하고, 다른 프로젝트의 데이터·모델·프로세스와 공유 서비스를 변경하지 않는다. 사용자의 PDF를 임의로 탐색하거나 전송하지 않는다. 기존 폴더나 가상환경을 덮어쓰지 않는다.
2. Windows PowerShell에서 아래 명령으로 Python과 하드웨어를 확인한다. GPU 이름은 표시되지만 VRAM·드라이버 호환성·GPU 추론 지원 여부는 이 도구가 판정하지 않는다.

   ```powershell
   py -3.12 --version
   .\scripts\doctor.ps1
   ```

3. Python 3.12가 준비되지 않았거나 디스크 공간·설치 권한이 부족하면 원인을 보고하고 중단한다. 관리자 권한 상승이나 드라이버 변경을 임의로 하지 않는다. 준비되면 저장소 폴더에서 다음을 실행한다. 이 명령은 Python 패키지를 인터넷에서 받는다.

   ```powershell
   .\scripts\install.ps1
   .\.venv\Scripts\python.exe .\scripts\smoke_test.py
   ```

   JSON의 `core`가 `PASS`인지 확인한다. 이 시험은 임시 폴더의 합성 PDF와 빈 DB만 사용하며 실제 사용자 문헌과 모델을 읽지 않는다. `embedding`과 `reranker`의 `NOT_RUN`은 시험하지 않았다는 뜻이다. 실패하면 오류를 보고하고 다음 단계의 성공을 주장하지 않는다.

4. 사용자가 의미 검색까지 원하는 경우 `docs/ko/MODEL_ARTIFACTS.md`와 `docs/ko/SEMANTIC_SEARCH.md`를 읽는다. 모델별 공식 배포처·라이선스·예상 다운로드 크기와 디스크 공간을 안내하고, 사용자가 다운로드에 동의한 경우에만 아래 단계를 진행한다. 기존 공유 모델 캐시, LM Studio, WSL 또는 다른 서비스의 시작·종료를 강제하지 않는다.

   ```powershell
   .\scripts\install-ai.ps1
   $modelRoot = Join-Path $env:LOCALAPPDATA 'ArticleAI\models'
   .\.venv\Scripts\python.exe .\scripts\install_models.py --model embedding --destination $modelRoot --accept-license-and-download
   .\.venv\Scripts\python.exe .\scripts\install_models.py --model reranker --destination $modelRoot --accept-license-and-download
   .\.venv\Scripts\python.exe .\scripts\smoke_test.py --model-root $modelRoot --reranker
   ```

   다운로드 중단 시 미완료 모델에 대해 같은 명령을 다시 실행하면 부분 파일을 이어받고, 전체 파일이 완성된 뒤 해시를 검증한다. 파일 손상, 기존 완료 폴더 또는 예상 밖 파일이 있으면 자동 삭제하거나 덮어쓰지 말고 오류를 보고한다. `embedding`과 `reranker`가 각각 `PASS`일 때만 해당 PC의 합성 시험 통과로 기록한다. 이는 전체 모델 신규 설치나 검색 정확도·원본 제품 동등성을 보증하지 않는다. GPT-OSS는 설치기에서 별도로 받을 수 있지만 현재 앱에 연결되지 않으므로 실행이 필요하다고 주장하거나 자동으로 받지 않는다.

5. 다음 명령으로 앱을 실행하고 브라우저 `http://127.0.0.1:18531`을 연다. 포트가 이미 사용 중이라면 다른 서비스를 종료하지 말고 오류를 보고한다.

   ```powershell
   .\scripts\start.ps1
   ```

   `문헌 0건`을 확인한다. 사용자가 선택한 PDF만 `문헌 관리`에서 등록한 다음 `문헌 검색`과 `원고 검사`를 확인한다. 의미 검색 모델이 준비됐다면 `문헌 검색`의 `실험: CPU 의미 검색`에서 모델을 로드하고 색인을 생성한다. 결과의 PDF 페이지와 추출 텍스트를 사람이 확인한다. 스캔 PDF는 OCR이 없어 검색되지 않을 수 있다.

6. 실행 중인 PowerShell에서 Ctrl+C로 종료하고 재시작한 뒤, 등록된 문헌과 저장된 보고서가 유지되는지 확인한다. 데이터 백업 및 제거는 `docs/ko/INSTALL_WINDOWS.md`와 `docs/ko/ONTOLOGY_GUIDE.md`를 따른다. 임시 시험 외 사용자 DB를 삭제·초기화하지 않는다.
7. 설치 경로, 실행한 명령, 스모크 JSON, 브라우저 확인 결과, 원본 제품과 다른 기능, 실행하지 못한 항목을 구분하여 보고한다. `llm=NOT_IMPLEMENTED`, `gpu_profile=NOT_VERIFIED`를 임의로 성공으로 바꾸지 않는다. 공개 전환에는 이력·보안·라이선스·권리 검토가 별도로 필요하다.
