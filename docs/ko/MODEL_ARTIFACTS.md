# 모델 아티팩트 준비 — 실험 단계

`models.lock.json`은 개발 원본의 다운로드 메타데이터에서 확인한 revision 후보와 해당 revision에 대해 Hugging Face 공식 API가 제공한 파일 크기·해시를 기록합니다. 대체 원본 형식과 Metal 파일은 제외했습니다. 개발 모델 디렉터리의 GPT-OSS 가중치 3개와 Qwen 가중치 2개는 2026-10-28에 SHA-256을 직접 계산해 잠금 목록과 일치했습니다. 설정과 토크나이저 전체 및 실제 사용 중인 추론 백엔드는 검증하지 않았으므로 **기준 환경 재현 완료가 아닙니다**.

| 역할 | 공식 모델 카드 | 아티팩트 라이선스 |
|---|---|---|
| LLM | [openai/gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b) | Apache-2.0; 모델 카드와 사용 정책 확인 |
| 임베딩 | [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Apache-2.0 |
| 리랭커 | [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) | Apache-2.0 |

설치기는 모델을 Git에 넣지 않고, 사용자가 지정한 폴더로 공식 배포처에서 직접 받습니다. 파일별 크기와 LFS SHA-256 또는 Git blob 해시를 검증합니다. 파일 일부가 남으면 서버가 요청한 범위의 재개를 지원할 때 이어받습니다. 손상된 파일을 자동 삭제하지 않습니다. 부족한 디스크 공간, 해시 불일치, 기존 완료 폴더 또는 예상 밖 파일이 있으면 중단합니다. 오류가 생기면 `.partial` 폴더를 직접 확인하세요. 검토 없이 삭제하면 재개 가능한 데이터가 사라집니다.

실제 다운로드 전 각 모델 카드·라이선스를 확인하고 저장 공간과 네트워크 사용에 동의한 사용자만 다음을 실행합니다. 아래 경로는 예시이며 자신의 빈 모델 전용 폴더로 바꾸세요.

```powershell
.\.venv\Scripts\python.exe .\scripts\install_models.py --model embedding --destination "$env:LOCALAPPDATA\ArticleAI\models" --accept-license-and-download
.\.venv\Scripts\python.exe .\scripts\install_models.py --model reranker --destination "$env:LOCALAPPDATA\ArticleAI\models" --accept-license-and-download
.\.venv\Scripts\python.exe .\scripts\install_models.py --model llm --destination "$env:LOCALAPPDATA\ArticleAI\models" --accept-license-and-download
```

크기는 실행 시 바이트 단위로 표시됩니다. 다운로드는 수 GB 이상이며 전용 폴더에 충분한 여유 공간이 필요합니다. 설치기는 남은 예상 용량 외에 512 MiB를 확보하도록 검사합니다. 재개·오류 처리는 모의 응답으로, 작은 공식 설정 파일의 다운로드 및 해시는 실제 환경에서 시험했습니다. 임베딩·리랭커는 UI의 실험 CPU 검색에서 사용할 수 있습니다. LLM은 연결되지 않았으며 세 모델의 전체 다운로드, 서버 추론, GPU 메모리와 모델 품질은 **NOT_VERIFIED**입니다. 모델 설치만으로 전체 AI 기능이 작동한다고 판단하지 마세요.
