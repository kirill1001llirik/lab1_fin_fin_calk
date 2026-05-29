from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
import webbrowser

from .logic import CalculationError, calculate, calculate_two_operands, format_result


STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class FinancialCalculatorHandler(BaseHTTPRequestHandler):
    server_version = "FinancialCalculator/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"", "/"}:
            self._send_static_file(STATIC_DIR / "index.html")
            return

        requested = unquote(path).lstrip("/")
        target = (STATIC_DIR / requested).resolve()
        static_root = STATIC_DIR.resolve()

        try:
            target.relative_to(static_root)
        except ValueError:
            self.send_error(404)
            return

        if not target.is_file():
            self.send_error(404)
            return

        self._send_static_file(target)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/calculate":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise CalculationError("Некорректный запрос.")

            if "operands" in payload:
                calculation = calculate(
                    _payload_sequence(payload.get("operands")),
                    _payload_sequence(payload.get("operations")),
                    str(payload.get("rounding", "math")),
                )
                response = {
                    "ok": True,
                    "result": format_result(calculation.value),
                    "rounded": format_result(calculation.rounded, max_fraction_digits=0),
                }
            else:
                result = calculate_two_operands(
                    str(payload.get("left", "")),
                    str(payload.get("right", "")),
                    str(payload.get("operation", "")),
                )
                response = {"ok": True, "result": format_result(result)}
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"ok": False, "error": "Некорректный запрос."}, status=400)
        except CalculationError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            print(f"Ошибка обработки запроса: {exc!r}", file=sys.stderr)
            self._send_json({"ok": False, "error": "Не удалось выполнить расчет."}, status=500)
        else:
            self._send_json(response)

    def log_message(self, format: str, *args: object) -> None:
        print("%s - %s" % (self.address_string(), format % args))

    def _send_static_file(self, path: Path) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript"}:
            content_type += "; charset=utf-8"

        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    try:
        return ThreadingHTTPServer((host, port), FinancialCalculatorHandler)
    except OSError:
        if port == 0:
            raise
        return ThreadingHTTPServer((host, 0), FinancialCalculatorHandler)


def _payload_sequence(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the financial calculator web application.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    server = create_server(args.host, args.port)
    host, port = server.server_address
    url = f"http://{host}:{port}/"

    print(f"Финансовый калькулятор запущен: {url}", flush=True)
    print("Нажмите Ctrl+C в этом окне, чтобы остановить сервер.", flush=True)

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main(sys.argv[1:])
