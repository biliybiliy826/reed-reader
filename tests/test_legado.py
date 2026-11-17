import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from reed_reader.legado import Legado, NetworkFailure, from_utf16, to_utf16


@pytest.fixture
def service():
    state = {"requests": [], "posts": [], "fail": False}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            state["requests"].append((parsed.path, query))
            if parsed.path == "/getBookshelf":
                data = [{"bookUrl": "https://book.test/书?a=1&b=2", "name": "网络书", "author": "苇读",
                         "durChapterIndex": 0, "durChapterPos": 3}]
            elif parsed.path == "/getChapterList":
                data = [{"title": "第一章"}, {"title": "第二章"}]
            else:
                data = "甲😀乙\n" + "这是可离线阅读的网络正文。" * 70
            response = {"isSuccess": not state["fail"], "data": data, "errorMsg": "模拟服务故障"}
            raw = json.dumps(response, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            state["posts"].append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            raw = b'{"isSuccess": true, "data": null}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    yield endpoint, state
    server.shutdown()
    server.server_close()
    thread.join()


def test_full_protocol_and_utf16_positions(service):
    endpoint, state = service
    client = Legado(endpoint)
    remote = client.bookshelf()[0]
    book = client.book(remote)
    content = client.content(remote.url, 0)
    assert book.chapters[0].text is None
    assert state["requests"][-1][1] == {"url": [remote.url], "index": ["0"]}
    assert from_utf16(content, 3) == 2
    assert to_utf16(content, 2) == 3
    client.push(remote, 0, 2, content, "第一章")
    route, payload = state["posts"][0]
    assert route == "/saveBookProgress"
    assert payload["durChapterPos"] == 3
    assert payload["name"] == remote.title
    assert payload["durChapterIndex"] == 0


def test_server_error_is_not_blank_content(service):
    endpoint, state = service
    state["fail"] = True
    with pytest.raises(NetworkFailure, match="模拟服务故障"):
        Legado(endpoint).content("book", 0)


@pytest.mark.parametrize("endpoint", ["file:///tmp/a", "192.168.1.1", "http://u:p@phone", "http://phone:a", "https://phone?token=x"])
def test_invalid_endpoints(endpoint):
    with pytest.raises(NetworkFailure):
        Legado(endpoint)
