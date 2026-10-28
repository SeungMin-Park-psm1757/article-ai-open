# ARTICLE AI Community Edition

연구자가 보유한 PDF를 로컬에서 등록하고 검색하는 **개발 중인 후보**입니다. 현재 PDF 텍스트 추출, 페이지 단위 문자 검색, 정확한 문장 일치 검사와 Markdown 보고서를 제공합니다. 문자 일치는 표절 판정이 아닙니다.

[설치 안내](docs/ko/INSTALL_WINDOWS.md) · [배포 설계와 기능 상태](docs/ko/ARCHITECTURE.md) · [모델 준비](docs/ko/MODEL_ARTIFACTS.md) · [개념 관리](docs/ko/ONTOLOGY_GUIDE.md) · [보안과 라이선스](docs/ko/SECURITY_AND_LICENSE.md)

## Windows 설치와 실행

Python 3.12와 인터넷이 필요합니다. PowerShell에서 이 폴더로 이동한 뒤:

```powershell
.\scripts\doctor.ps1
.\scripts\install.ps1
.\.venv\Scripts\python.exe .\scripts\smoke_test.py
.\scripts\start.ps1
```

진단은 OS·CPU·RAM·디스크·GPU 이름과 드라이버를 표시합니다. GPU 메모리와 모델 호환성은 확인하지 못하므로 하드웨어 프로필은 `UNVERIFIED`입니다.
스모크 테스트는 직접 만든 합성 PDF로 동작을 확인하며 사용자의 문헌을 읽지 않습니다. 모델을 시험하지 않았다면 `embedding`과 `reranker`는 `NOT_RUN`입니다.

브라우저에서 `http://127.0.0.1:18531`을 엽니다. 종료하려면 PowerShell에서 Ctrl+C를 누릅니다. 포트가 사용 중이면 충돌 원인을 확인하세요.

처음 문헌은 0건입니다. 사용 권한이 있는 텍스트 PDF를 등록하세요. 개발자의 PDF와 색인은 포함되지 않습니다. PDF는 사용자 홈의 `ArticleAI-data/documents.sqlite3`에 저장됩니다. 백업은 앱 종료 후 해당 파일을 복사하세요. 제거하려면 앱을 종료하고 데이터 폴더와 설치 폴더를 삭제합니다. 등록 문헌이 삭제되므로 필요한 백업을 먼저 보관하세요.

## 현재 제한

- OCR, LLM과 폴더 일괄 등록은 미구현입니다. [CPU 의미 검색 및 리랭킹](docs/ko/SEMANTIC_SEARCH.md)은 모델과 의존성을 별도 설치하는 실험 경로입니다. 문헌 관리 탭에서 제목을 변경하거나 확인 후 삭제할 수 있습니다. 보고서는 데이터베이스에 저장됩니다. 별도로 [사용자가 직접 관리하는 개념 사전](docs/ko/ONTOLOGY_GUIDE.md)을 제공하며 의미 관계 자동 판정은 지원하지 않습니다.
- 검색은 문자 부분 일치이며 최대 100페이지를 표시합니다. 원고 검사는 20자 이상 문장의 정확한 일치만 찾습니다.
- 원고 검사의 각 문장은 최대 100페이지까지만 비교 결과에 표시됩니다. 저장된 보고서는 검사 당시의 기록이며 문헌을 삭제해도 남습니다. 문헌 ID는 삭제 후 재사용될 수 있으므로 보고서의 ID만으로 현재 문헌을 식별하지 마세요.
- 암호화 PDF, 500쪽 초과 또는 30MB 초과 PDF는 지원하지 않습니다. 이미지 PDF에는 검색 가능한 텍스트가 없을 수 있습니다.
- 원본 PDF는 문헌 등록 탭에서 내려받아 페이지를 확인합니다.
- 공개 후보 코드의 라이선스는 [Apache-2.0](LICENSE)입니다. 별도로 다운로드하는 모델·의존성과 사용자가 제공하는 문헌에는 각자의 라이선스와 권리가 적용됩니다. 전체 모델 재현과 공개용 보안 검증은 진행 중입니다.

Codex를 이용할 경우 [CODEX_SETUP.md](CODEX_SETUP.md)를 참고하세요. [모델 아티팩트 준비](docs/ko/MODEL_ARTIFACTS.md)는 별도의 실험 단계이며, 완전한 모델 재현 설치는 아직 제공하지 않습니다.

Codex에 전달할 문구: `이 저장소의 CODEX_SETUP.md를 읽고, 보호 경계를 지키면서 내 PC에 ARTICLE AI를 설치하고 검증해 줘.`
