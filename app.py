import os
from pathlib import Path

import streamlit as st

import core
import ontology
import semantic

st.set_page_config(page_title='ARTICLE AI', layout='wide')
st.title('ARTICLE AI · 공개 배포 후보')
st.caption('로컬 검색 실험판 · CPU 의미 검색은 선택 기능입니다. LLM과 OCR은 아직 연결되지 않았습니다.')
data_root = Path(os.environ.get('ARTICLE_AI_DATA_DIR', Path.home() / 'ArticleAI-data'))
db = core.connect(data_root / 'documents.sqlite3')
documents = db.execute('SELECT id,title FROM documents ORDER BY id').fetchall()
st.write(f'문헌 {len(documents)}건' if documents else '문헌 0건 · 사용 권한이 있는 PDF를 등록하세요.')
if 'upload_result' in st.session_state:
    count = st.session_state.pop('upload_result')
    st.toast(f'등록했습니다. 텍스트가 추출된 페이지: {count}개.')
    if not count:
        st.toast('텍스트를 추출하지 못했습니다. OCR은 지원하지 않습니다.')
upload_tab, search_tab, inspect_tab, report_tab, concept_tab = st.tabs(['문헌 관리', '문헌 검색', '원고 검사', '저장된 보고서', '개념 관리'])
with upload_tab:
    with st.form('upload', clear_on_submit=True):
        pdf = st.file_uploader('PDF', type=['pdf'], max_upload_size=30)
        title = st.text_input('제목')
        submit = st.form_submit_button('등록')
        if submit:
            try:
                if pdf is None:
                    raise ValueError('PDF를 선택하세요.')
                _, count = core.add_pdf(db, title, pdf.getvalue())
                st.session_state.upload_result = count
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    for doc_id, doc_title in documents:
        with st.expander(doc_title):
            raw = db.execute('SELECT pdf FROM documents WHERE id=?', (doc_id,)).fetchone()[0]
            st.download_button('원본 PDF 다운로드', raw, f'document-{doc_id}.pdf', 'application/pdf', key=f'pdf-{doc_id}')
            with st.form(f'rename-{doc_id}'):
                new_title = st.text_input('문헌 제목', value=doc_title)
                if st.form_submit_button('제목 저장'):
                    try:
                        core.rename_document(db, doc_id, new_title)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            with st.form(f'delete-{doc_id}'):
                confirmed = st.checkbox('이 문헌과 추출된 텍스트를 삭제합니다')
                if st.form_submit_button('문헌 삭제'):
                    if confirmed:
                        core.delete_document(db, doc_id)
                        st.rerun()
                    else:
                        st.warning('삭제 확인을 선택하세요.')
with search_tab:
    query = st.text_input('검색어')
    if query:
        results = core.search(db, query)
        st.write(f'{len(results)}개 페이지 (최대 100개)')
        for doc_id, doc_title, page, text in results:
            st.markdown(f'**문헌 {doc_id} · {page}쪽**')
            st.write(doc_title)
            st.text(text[:2000])
    with st.expander('실험: CPU 의미 검색'):
        st.caption('설치·검증된 Qwen 임베딩 모델을 CPU에 로드합니다. 2,000개 구간까지 지원하며 원본 검색 품질과 동일하다고 검증되지 않았습니다.')
        default_models = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ArticleAI' / 'models'
        root = st.text_input('모델 폴더', value=str(default_models))
        if st.button('모델 파일 확인 및 로드'):
            for key in ('semantic_model', 'semantic_model_root', 'reranker', 'reranker_root'):
                st.session_state.pop(key, None)
            try:
                with st.spinner('파일을 검증하고 CPU에 모델을 로드하고 있습니다. 시간이 걸릴 수 있습니다.'):
                    st.session_state.semantic_model = semantic.load_model(root)
                    st.session_state.semantic_model_root = root
                st.success('임베딩 모델을 로드했습니다.')
            except (OSError, ValueError, RuntimeError) as exc:
                st.error(str(exc))
        if 'semantic_model' in st.session_state and st.session_state.get('semantic_model_root') == root:
            model = st.session_state.semantic_model
            if st.button('의미 색인 생성 또는 갱신'):
                try:
                    with st.spinner('문헌을 CPU로 색인하고 있습니다.'):
                        count = semantic.rebuild(db, model)
                    st.success(f'{count}개 구간의 색인을 저장했습니다.')
                except (OSError, ValueError, RuntimeError) as exc:
                    st.error(str(exc))
            if st.button('리랭커 파일 확인 및 로드'):
                st.session_state.pop('reranker', None)
                st.session_state.pop('reranker_root', None)
                try:
                    with st.spinner('리랭커 파일을 검증하고 CPU에 로드하고 있습니다.'):
                        st.session_state.reranker = semantic.load_reranker(root)
                        st.session_state.reranker_root = root
                    st.success('리랭커를 로드했습니다.')
                except (OSError, ValueError, RuntimeError) as exc:
                    st.error(str(exc))
            use_reranker = st.checkbox('검색 결과 리랭킹 사용')
            semantic_query = st.text_input('의미 검색어')
            if st.button('의미 검색'):
                try:
                    with st.spinner('검색 중입니다.'):
                        results = semantic.search(db, model, semantic_query)
                        if use_reranker:
                            if 'reranker' not in st.session_state or st.session_state.get('reranker_root') != root:
                                raise ValueError('같은 모델 폴더에서 리랭커를 먼저 로드하세요.')
                            ranked = semantic.rerank(db, st.session_state.reranker, semantic_query, results)
                        else:
                            ranked = [(None, item) for item in results]
                    if not results:
                        st.info('검색 결과가 없습니다.')
                    for rerank_score, (score, doc_id, title, page, start, end, passage) in ranked:
                        score_text = f' · 리랭커 점수 {rerank_score:.3f}' if rerank_score is not None else ''
                        st.write(f'{title} · {page}쪽 · 글자 {start}–{end} · 유사도 {score:.3f}{score_text}')
                        st.text(passage)
                except (OSError, ValueError, RuntimeError) as exc:
                    st.error(str(exc))
with inspect_tab:
    manuscript = st.text_area('검사할 원고', height=200)
    if st.button('문자 일치 검사'):
        try:
            matches = core.inspect(db, manuscript)
            st.caption('20자 이상 문장의 정확한 문자 일치만 확인합니다. 표절이나 의미상 유사성의 판정이 아닙니다.')
            lines = ['# 문자 일치 검사 결과', '', '검사 당시의 기록입니다. 자동 일치는 사람의 검토가 필요합니다.', '각 문장의 일치 결과는 전체 문헌에서 최대 100페이지로 제한됩니다.', '']
            for passage, doc_id, doc_title, page in matches:
                st.write(f'{doc_title} · {page}쪽', passage)
                lines.append(f'- 문헌 {doc_id} · {page}쪽: {passage}')
            if not matches:
                st.info('일치하는 문장이 없습니다.')
                lines.append('일치 항목 없음.')
            report_id = core.save_report(db, '\n'.join(lines))
            st.success(f'보고서 {report_id}번을 저장했습니다. 저장된 보고서 탭에서 다운로드하세요.')
        except ValueError as exc:
            st.error(str(exc))
with report_tab:
    reports = db.execute('SELECT id,created_at,content FROM reports ORDER BY id DESC').fetchall()
    if not reports:
        st.info('저장된 보고서가 없습니다.')
    for report_id, created_at, content in reports:
        with st.expander(f'보고서 {report_id} · {created_at} UTC'):
            st.text(content)
            st.download_button('보고서 다운로드', content, f'report-{report_id}.md', 'text/markdown', key=f'report-{report_id}')
with concept_tab:
    st.caption('사용자가 직접 만든 개념과 문헌 연결입니다. AI 추론이나 지지·반박 판정이 아닙니다. 스키마 v1. 비활성화해도 기존 연결은 유지됩니다.')
    with st.form('add-concept', clear_on_submit=True):
        concept_name = st.text_input('새 개념 이름')
        if st.form_submit_button('개념 추가'):
            try:
                ontology.add_concept(db, concept_name)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    concepts = db.execute('SELECT id,label FROM ontology_concepts WHERE active=1 ORDER BY label').fetchall()
    if not concepts:
        st.info('등록된 개념이 없습니다.')
    for concept_id, label in concepts:
        with st.expander(label):
            with st.form(f'concept-rename-{concept_id}'):
                new_label = st.text_input('개념 이름', value=label)
                if st.form_submit_button('개념 이름 저장'):
                    try:
                        ontology.rename_concept(db, concept_id, new_label)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            links = db.execute('''SELECT d.id,d.title FROM ontology_document_links l
                JOIN documents d ON d.id=l.document_id WHERE l.concept_id=? ORDER BY d.id''', (concept_id,)).fetchall()
            for doc_id, doc_title in links:
                st.write(f'연결: {doc_title}')
                if st.button('연결 해제', key=f'unlink-{concept_id}-{doc_id}'):
                    ontology.unlink_document(db, concept_id, doc_id)
                    st.rerun()
            available = [(doc_id, title) for doc_id, title in documents if doc_id not in {item[0] for item in links}]
            if available:
                with st.form(f'link-{concept_id}'):
                    chosen = st.selectbox('연결할 문헌', available, format_func=lambda item: f'{item[1]} (ID {item[0]})')
                    if st.form_submit_button('문헌 연결'):
                        ontology.link_document(db, concept_id, chosen[0])
                        st.rerun()
            with st.form(f'deactivate-{concept_id}'):
                confirm = st.checkbox('개념을 비활성화합니다')
                if st.form_submit_button('개념 비활성화'):
                    if confirm:
                        ontology.deactivate_concept(db, concept_id)
                        st.rerun()
                    else:
                        st.warning('비활성화 확인을 선택하세요.')
    inactive = db.execute('SELECT id,label FROM ontology_concepts WHERE active=0 ORDER BY label').fetchall()
    if inactive:
        with st.expander('비활성 개념'):
            for concept_id, label in inactive:
                st.write(label)
                if st.button('다시 활성화', key=f'reactivate-{concept_id}'):
                    ontology.reactivate_concept(db, concept_id)
                    st.rerun()
    with st.expander('변경 이력'):
        for created_at, action, details in db.execute('SELECT created_at,action,details FROM ontology_history ORDER BY id DESC LIMIT 100'):
            st.text(f'{created_at} UTC · {action}\n{details}')
