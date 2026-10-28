import http.client
import io
import json
import logging
from pathlib import Path
import runpy
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from app import server
from app.llm import FakeLLM
from tests.test_review_deadline import assert_id, assert_log


@pytest.fixture
def serve():
    running = []

    def start(llm=None):
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.ReviewHandler)
        httpd.llm = llm if llm is not None else FakeLLM()
        thread = threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': 0.01})
        thread.start()
        running.append((httpd, thread))
        return httpd

    yield start
    for httpd, thread in running:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def request(httpd, method, path, body=None):
    connection = http.client.HTTPConnection(*httpd.server_address, timeout=2)
    try:
        connection.request(method, path, body=body, headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


@pytest.mark.parametrize('status, payload', [
    (504, {'error': {'code': 'llm_timeout'}, 'request_id': 'server-id'}),
    (200, {'summary': 'Привет', 'risks': [], 'checks': [], 'request_id': 'server-id'}),
])
def test_post_forwards_public_result_and_fixed_deadline(serve, monkeypatch, status, payload):
    llm = FakeLLM()
    httpd = serve(llm)
    seen = []

    def handle(body, adapter, *, deadline_s):
        seen.append((body, adapter, deadline_s))
        return status, payload

    monkeypatch.setattr(server, 'handle_review', handle)
    body = b'{"diff":"example","deadline_s":0,"request_id":"client"}'
    actual, headers, data = request(httpd, 'POST', '/api/reviews', body)
    assert actual == status
    assert json.loads(data) == payload
    assert headers['Content-Type'] == 'application/json; charset=utf-8'
    assert int(headers['Content-Length']) == len(data)
    assert seen == [(body, llm, 10.0)]


def test_real_post_uses_adapter_of_each_server_and_logs_once(serve, caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    for label in ['first', 'second']:
        llm = FakeLLM(result={'summary': label, 'risks': [], 'checks': []})
        status, _, data = request(serve(llm), 'POST', '/api/reviews', b'{"diff":"example"}')
        payload = json.loads(data)
        assert status == 200
        assert payload['summary'] == label
        assert_id(payload)
        assert llm.calls == ['example']
        assert_log(caplog, status, payload)
        caplog.clear()


@pytest.mark.parametrize('method', ['POST', 'GET'])
def test_unknown_route_is_404_without_review_log(serve, caplog, method):
    caplog.set_level(logging.INFO, logger='reviews')
    assert request(serve(), method, '/unknown')[0] == 404
    assert not caplog.records


def test_get_reads_exact_html_on_each_request_independent_of_cwd(serve, monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    monkeypatch.chdir(tmp_path)
    httpd = serve()
    status, headers, data = request(httpd, 'GET', '/')
    assert status == 200
    assert data == (Path(server.__file__).resolve().parent / 'static' / 'index.html').read_bytes()
    assert headers['Content-Type'] == 'text/html; charset=utf-8'
    assert int(headers['Content-Length']) == len(data)
    page = tmp_path / 'index.html'
    monkeypatch.setattr(server, 'INDEX_PATH', page)
    for content in ['<h1>Первый</h1>', '<h1>Второй</h1>']:
        page.write_text(content, encoding='utf-8')
        status, headers, data = request(httpd, 'GET', '/')
        assert status == 200
        assert data == content.encode('utf-8')
        assert int(headers['Content-Length']) == len(data)
    page.unlink()
    status, _, data = request(httpd, 'GET', '/')
    assert status == 404
    assert str(page).encode() not in data
    assert not caplog.records


@pytest.mark.parametrize('args, port, delay', [
    ([], 8000, 0.0), (['0', '--llm', 'ok'], 0, 0.0),
    (['0', '--llm', 'slow'], 0, 12.0),
    (['0', '--llm', 'fail'], 0, 0.0),
])
def test_cli_configures_instance_before_serving(monkeypatch, args, port, delay):
    instances = []

    class StartupProbe:
        def __init__(self, address, handler):
            self.address = address
            self.handler = handler
            instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def serve_forever(self):
            assert isinstance(self.llm, FakeLLM)
            assert self.llm.delay_s == delay
            if 'fail' in args:
                assert isinstance(self.llm.error, RuntimeError)
                assert str(self.llm.error) == 'demo failure'
            else:
                assert self.llm.error is None

    # Only replace the long-lived serving boundary; execute the real module CLI.
    monkeypatch.setattr('http.server.ThreadingHTTPServer', StartupProbe)
    monkeypatch.setattr(sys, 'argv', ['app.server', *args])
    runpy.run_path(server.__file__, run_name='__main__')
    assert len(instances) == 1
    assert instances[0].address == ('127.0.0.1', port)


@pytest.mark.parametrize('args, success', [
    (['--help'], True), (['bad-port'], False),
    (['--llm', 'unknown'], False), (['--unknown'], False),
])
def test_cli_exits_before_serving_for_help_or_bad_arguments(args, success):
    result = subprocess.run([sys.executable, '-m', 'app.server', *args],
                            capture_output=True, text=True, timeout=3)
    assert (result.returncode == 0) == success
    assert 'usage:' in result.stdout + result.stderr


def test_import_does_not_parse_arguments_or_start_server():
    result = subprocess.run([sys.executable, '-c',
                             'import sys; sys.argv = ["server", "--bad"]; import app.server'],
                            capture_output=True, text=True, timeout=3)
    assert result.returncode == 0
    assert not result.stdout + result.stderr


def test_real_http_failure_is_safe_and_get_still_works(serve, caplog):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM(error=RuntimeError('demo failure'))
    httpd = serve(llm)
    status, _, data = request(httpd, 'POST', '/api/reviews', b'{"diff":"example"}')
    payload = json.loads(data)
    assert status == 502
    assert_id(payload)
    assert payload == {'error': {'code': 'llm_failed'}, 'request_id': payload['request_id']}
    assert llm.calls == ['example']
    assert request(httpd, 'GET', '/')[2] == server.INDEX_PATH.read_bytes()
    assert_log(caplog, status, payload)
    assert 'demo failure' not in data.decode() + caplog.text
    assert 'RuntimeError' not in data.decode() + caplog.text


@pytest.mark.parametrize('mode', ['ok', 'slow', 'fail'])
@pytest.mark.parametrize('body, expected_status, code', [
    (b'{}', 422, 'invalid_request'),
    (json.dumps({'diff': '😀' * 20001}).encode(), 413, 'diff_too_large'),
])
def test_http_validation_precedes_dependency(serve, caplog, mode, body, expected_status, code):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM(delay_s=12.0 if mode == 'slow' else 0,
                  error=RuntimeError('demo failure') if mode == 'fail' else None)
    status, _, data = request(serve(llm), 'POST', '/api/reviews', body)
    payload = json.loads(data)
    assert status == expected_status
    assert_id(payload)
    assert payload == {'error': {'code': code}, 'request_id': payload['request_id']}
    assert llm.calls == []
    assert_log(caplog, status, payload)


@pytest.mark.parametrize('failure', [BrokenPipeError, ConnectionResetError])
@pytest.mark.parametrize('stage', ['headers', 'body'])
def test_disconnect_preserves_outcome_without_traceback(failure, stage, caplog, capsys):
    caplog.set_level(logging.INFO, logger='reviews')
    llm = FakeLLM()
    handler = server.ReviewHandler.__new__(server.ReviewHandler)
    handler.path = '/api/reviews'
    body = b'{"diff":"example"}'
    handler.headers = {'Content-Length': str(len(body))}
    handler.rfile = io.BytesIO(body)
    handler.server = SimpleNamespace(llm=llm)
    statuses = []
    handler.send_response = statuses.append
    handler.send_header = lambda *args: None

    def disconnected(*args):
        raise failure('private connection diagnostic')

    handler.end_headers = disconnected if stage == 'headers' else lambda: None
    handler.wfile = SimpleNamespace(write=disconnected)
    handler.do_POST()
    assert statuses == [200]
    assert llm.calls == ['example']
    records = [r for r in caplog.records if r.name == 'reviews']
    assert len(records) == 1
    request_id = dict(part.split('=') for part in records[0].getMessage().split())['request_id']
    assert_id({'request_id': request_id})
    assert_log(caplog, 200, {'request_id': request_id})
    assert 'private' not in caplog.text
    assert capsys.readouterr().err == ''
