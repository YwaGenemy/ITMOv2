import inspect
import json
import logging
import time
import uuid

import pytest

from app.llm import FakeLLM
from app.review import handle_review


def assert_id(payload):
    value = payload['request_id']
    parsed = uuid.UUID(hex=value)
    assert parsed.version == 4
    assert parsed.hex == value


def assert_log(caplog, status, payload):
    records = [r for r in caplog.records if r.name == 'reviews']
    assert len(records) == 1
    record = records[0]
    fields = dict(part.split('=', 1) for part in record.getMessage().split())
    assert set(fields) == {'request_id', 'duration_ms', 'status'}
    assert fields['request_id'] == payload['request_id']
    assert int(fields['status']) == status
    assert int(fields['duration_ms']) >= 0
    assert record.exc_info is None
    assert record.stack_info is None


def test_timeout_returns_before_dependency_and_late_success_changes_nothing(caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM(delay_s=1.0, result={'summary': 'private result'})
    started = time.monotonic()
    status, payload = handle_review(b'{"diff":"private diff"}', llm, deadline_s=0.1)
    assert time.monotonic() - started <= 0.5
    assert status == 504
    assert_id(payload)
    assert payload == {'error': {'code': 'llm_timeout'}, 'request_id': payload['request_id']}
    saved = json.dumps(payload)
    assert_log(caplog, status, payload)
    time.sleep(1.05)
    assert json.dumps(payload) == saved
    assert llm.calls == ['private diff']
    assert_log(caplog, status, payload)


@pytest.mark.parametrize('result', [
    {'summary': 'private result', 'risks': [
        {'file': 'a.py', 'line': 1, 'evidence': 'changed', 'risk': 'failure'}
    ], 'checks': ['check'], 'request_id': 'model-id'},
    {'summary': 12, 'risks': [1, 2, 3, 4], 'checks': None},
    {},
])
def test_timely_result_is_preserved_with_server_id(result, caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM(result=result, delay_s=0.02)
    status, payload = handle_review(
        b'{"diff":"private diff","request_id":"client-id","deadline_s":0}',
        llm, deadline_s=0.5)
    assert status == 200
    assert_id(payload)
    assert payload['request_id'] not in ('model-id', 'client-id')
    assert {k: v for k, v in payload.items() if k != 'request_id'} == {
        k: v for k, v in result.items() if k != 'request_id'}
    assert llm.calls == ['private diff']
    assert_log(caplog, status, payload)
    assert inspect.signature(handle_review).parameters['deadline_s'].default == 10.0


def test_early_exception_is_safe_502(caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM(error=RuntimeError('private exception marker'))
    status, payload = handle_review(b'{"diff":"private diff"}', llm, deadline_s=0.5)
    assert status == 502
    assert_id(payload)
    assert payload == {'error': {'code': 'llm_failed'}, 'request_id': payload['request_id']}
    assert llm.calls == ['private diff']
    assert_log(caplog, status, payload)
    assert 'private' not in json.dumps(payload) + caplog.text
    assert 'RuntimeError' not in json.dumps(payload) + caplog.text


def test_late_exception_cannot_replace_timeout_or_escape_thread(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger='reviews')
    unhandled = []
    monkeypatch.setattr('threading.excepthook', unhandled.append)
    llm = FakeLLM(delay_s=1.0, error=RuntimeError('private exception marker'))
    status, payload = handle_review(b'{"diff":"private diff"}', llm, deadline_s=0.1)
    assert status == 504
    assert_id(payload)
    saved = json.dumps(payload)
    time.sleep(1.05)
    assert json.dumps(payload) == saved
    assert llm.calls == ['private diff']
    assert not unhandled
    assert_log(caplog, status, payload)


@pytest.mark.parametrize('body, expected_status, code', [
    (b'not-json', 422, 'invalid_request'),
    (json.dumps({'diff': 'private diff' * 2000}).encode(), 413, 'diff_too_large'),
])
def test_validation_errors_have_id_and_one_safe_log(body, expected_status, code, caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM(result={'summary': 'private result'}, error=RuntimeError('private exception'))
    status, payload = handle_review(body, llm)
    assert status == expected_status
    assert_id(payload)
    assert payload == {'error': {'code': code}, 'request_id': payload['request_id']}
    assert llm.calls == []
    assert_log(caplog, status, payload)
    assert 'private' not in caplog.text
