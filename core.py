"""Local document store. Each PDF and its extracted pages share one transaction."""
import hashlib
import io
import re
import sqlite3
from pathlib import Path

from pypdf import PdfReader
import ontology

MAX_PDF_BYTES = 30 * 1024 * 1024


def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL, pdf BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS pages (
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            page INTEGER NOT NULL, text TEXT NOT NULL,
            PRIMARY KEY(document_id, page));
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            content TEXT NOT NULL);
    ''')
    try:
        ontology.initialize(db)
    except Exception:
        db.close()
        raise
    return db


def add_pdf(db, title, data):
    title = title.strip()
    if not title or len(title) > 200:
        raise ValueError('제목은 1~200자로 입력하세요.')
    if not data.startswith(b'%PDF-') or len(data) > MAX_PDF_BYTES:
        raise ValueError('30 MB 이하의 PDF 파일을 선택하세요.')
    digest = hashlib.sha256(data).hexdigest()
    if db.execute('SELECT 1 FROM documents WHERE sha256=?', (digest,)).fetchone():
        raise ValueError('이미 등록된 PDF입니다.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted or not 0 < len(reader.pages) <= 500:
            raise ValueError('암호화 PDF 또는 500쪽 초과 PDF는 지원하지 않습니다.')
        pages = [(i + 1, page.extract_text() or '') for i, page in enumerate(reader.pages)]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('PDF를 읽을 수 없습니다.') from exc
    with db:
        doc_id = db.execute('INSERT INTO documents(sha256,title,pdf) VALUES(?,?,?)',
                            (digest, title, data)).lastrowid
        db.executemany('INSERT INTO pages VALUES(?,?,?)',
                       [(doc_id, number, text) for number, text in pages])
    return doc_id, sum(bool(text.strip()) for _, text in pages)


def search(db, query, max_length=200):
    query = query.strip()
    if not query or len(query) > max_length:
        return []
    # instr treats percent and underscore as ordinary characters.
    return db.execute('''SELECT d.id,d.title,p.page,p.text FROM pages p
        JOIN documents d ON d.id=p.document_id
        WHERE instr(lower(p.text), lower(?)) > 0 ORDER BY d.id,p.page LIMIT 100''',
        (query,)).fetchall()


def inspect(db, manuscript):
    passages = [s.strip() for s in re.split(r'[\n.!?]+', manuscript) if len(s.strip()) >= 20]
    if len(manuscript) > 100000 or len(passages) > 100:
        raise ValueError('원고는 10만 자와 문장 100개 이하여야 합니다.')
    matches = []
    for passage in passages:
        for doc_id, title, page, _ in search(db, passage, max_length=100000):
            matches.append((passage, doc_id, title, page))
    return matches


def rename_document(db, doc_id, title):
    title = title.strip()
    if not title or len(title) > 200:
        raise ValueError('제목은 1~200자로 입력하세요.')
    with db:
        if db.execute('UPDATE documents SET title=? WHERE id=?', (title, doc_id)).rowcount != 1:
            raise ValueError('문헌을 찾을 수 없습니다.')


def delete_document(db, doc_id):
    with db:
        ontology.record_document_deletion(db, doc_id)
        if db.execute('DELETE FROM documents WHERE id=?', (doc_id,)).rowcount != 1:
            raise ValueError('문헌을 찾을 수 없습니다.')


def save_report(db, content):
    with db:
        return db.execute('INSERT INTO reports(content) VALUES(?)', (content,)).lastrowid
