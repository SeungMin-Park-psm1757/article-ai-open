"""Versioned, user-curated concept tags; this is not an inferred knowledge graph."""
import json
import sqlite3
import unicodedata

SCHEMA_VERSION = 1


def initialize(db):
    """Create v1 transactionally, or reject a database from a newer version."""
    with db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('CREATE TABLE IF NOT EXISTS ontology_schema (version INTEGER NOT NULL)')
        versions = db.execute('SELECT version FROM ontology_schema').fetchall()
        if len(versions) > 1 or (versions and versions[0][0] != SCHEMA_VERSION):
            raise RuntimeError('지원하지 않는 개념 스키마 버전입니다. 데이터를 백업하고 호환 버전을 사용하세요.')
        if not versions:
            db.execute('CREATE TABLE ontology_concepts (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, normalized TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)))')
            db.execute('CREATE TABLE ontology_document_links (concept_id INTEGER NOT NULL REFERENCES ontology_concepts(id), document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE, PRIMARY KEY(concept_id, document_id))')
            db.execute('CREATE TABLE ontology_history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, action TEXT NOT NULL, details TEXT NOT NULL)')
            db.execute('INSERT INTO ontology_schema(version) VALUES(?)', (SCHEMA_VERSION,))


def _label(label):
    value = ' '.join(unicodedata.normalize('NFKC', label).split())
    if not value or len(value) > 100:
        raise ValueError('개념 이름은 1~100자로 입력하세요.')
    return value, value.casefold()


def _record(db, action, details):
    db.execute('INSERT INTO ontology_history(action, details) VALUES(?,?)',
               (action, json.dumps(details, ensure_ascii=False)))


def add_concept(db, label):
    label, normalized = _label(label)
    try:
        with db:
            concept_id = db.execute('INSERT INTO ontology_concepts(label,normalized) VALUES(?,?)', (label, normalized)).lastrowid
            _record(db, 'concept_added', {'concept_id': concept_id, 'label': label})
        return concept_id
    except sqlite3.IntegrityError as exc:
        raise ValueError('이미 존재하는 개념입니다.') from exc


def rename_concept(db, concept_id, label):
    label, normalized = _label(label)
    try:
        with db:
            previous = db.execute('SELECT label FROM ontology_concepts WHERE id=? AND active=1', (concept_id,)).fetchone()
            if not previous:
                raise ValueError('활성 개념을 찾을 수 없습니다.')
            db.execute('UPDATE ontology_concepts SET label=?,normalized=? WHERE id=?', (label, normalized, concept_id))
            _record(db, 'concept_renamed', {'concept_id': concept_id, 'before': previous[0], 'after': label})
    except sqlite3.IntegrityError as exc:
        raise ValueError('이미 존재하는 개념입니다.') from exc


def deactivate_concept(db, concept_id):
    with db:
        previous = db.execute('SELECT label FROM ontology_concepts WHERE id=? AND active=1', (concept_id,)).fetchone()
        if not previous:
            raise ValueError('활성 개념을 찾을 수 없습니다.')
        db.execute('UPDATE ontology_concepts SET active=0 WHERE id=?', (concept_id,))
        _record(db, 'concept_deactivated', {'concept_id': concept_id, 'label': previous[0]})


def reactivate_concept(db, concept_id):
    with db:
        previous = db.execute('SELECT label FROM ontology_concepts WHERE id=? AND active=0', (concept_id,)).fetchone()
        if not previous:
            raise ValueError('비활성 개념을 찾을 수 없습니다.')
        db.execute('UPDATE ontology_concepts SET active=1 WHERE id=?', (concept_id,))
        _record(db, 'concept_reactivated', {'concept_id': concept_id, 'label': previous[0]})


def link_document(db, concept_id, document_id):
    with db:
        concept = db.execute('SELECT label FROM ontology_concepts WHERE id=? AND active=1', (concept_id,)).fetchone()
        document = db.execute('SELECT sha256 FROM documents WHERE id=?', (document_id,)).fetchone()
        if not concept or not document:
            raise ValueError('활성 개념 또는 문헌을 찾을 수 없습니다.')
        try:
            db.execute('INSERT INTO ontology_document_links VALUES(?,?)', (concept_id, document_id))
        except sqlite3.IntegrityError as exc:
            raise ValueError('이미 연결된 문헌입니다.') from exc
        _record(db, 'document_linked', {'concept_id': concept_id, 'concept': concept[0], 'document_sha256': document[0]})


def unlink_document(db, concept_id, document_id):
    with db:
        document = db.execute('SELECT sha256 FROM documents WHERE id=?', (document_id,)).fetchone()
        if not document or db.execute('DELETE FROM ontology_document_links WHERE concept_id=? AND document_id=?', (concept_id, document_id)).rowcount != 1:
            raise ValueError('연결을 찾을 수 없습니다.')
        _record(db, 'document_unlinked', {'concept_id': concept_id, 'document_sha256': document[0]})


def record_document_deletion(db, document_id):
    document = db.execute('SELECT sha256 FROM documents WHERE id=?', (document_id,)).fetchone()
    if document:
        for (concept_id,) in db.execute('SELECT concept_id FROM ontology_document_links WHERE document_id=?', (document_id,)):
            _record(db, 'document_deleted', {'concept_id': concept_id, 'document_sha256': document[0]})
