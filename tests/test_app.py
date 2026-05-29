import json
import threading
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from financial_calculator.app import FinancialCalculatorHandler, create_server


class FinancialCalculatorApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.original_log_message = FinancialCalculatorHandler.log_message
        FinancialCalculatorHandler.log_message = lambda self, format, *args: None
        cls.server = create_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        FinancialCalculatorHandler.log_message = cls.original_log_message

    def post_raw(self, body: bytes, content_type: str = "application/json") -> tuple[int, dict[str, object]]:
        request = Request(
            self.base_url + "/api/calculate",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )

        try:
            with urlopen(request, timeout=5) as response:
                status = response.status
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            try:
                status = exc.code
                response_body = exc.read().decode("utf-8")
            finally:
                exc.close()
        except (OSError, TimeoutError, URLError) as exc:
            self.fail(f"HTTP request was interrupted instead of returning JSON: {exc!r}")

        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError as exc:
            self.fail(f"HTTP response is not JSON, status={status}, body={response_body!r}: {exc}")

        self.assertIsInstance(parsed, dict)
        self.assertIn("ok", parsed)
        return status, parsed

    def post_calculate(self, payload: object) -> tuple[int, dict[str, object]]:
        return self.post_raw(json.dumps(payload).encode("utf-8"))

    def assert_valid_probe_still_works(self) -> None:
        status, body = self.post_calculate(
            {
                "operands": ["0", "2", "3", "0"],
                "operations": ["+", "+", "+"],
                "rounding": "math",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True, "result": "5", "rounded": "5"})

    def test_errors_return_json_and_valid_request_still_works_afterward(self) -> None:
        overflow_status, overflow_body = self.post_calculate(
            {
                "operands": ["0", "99999999999", "99999999999", "0"],
                "operations": ["+", "*", "+"],
                "rounding": "math",
            }
        )
        self.assertEqual(overflow_status, 400)
        self.assertFalse(overflow_body["ok"])
        self.assertIn("Переполнение", overflow_body["error"])

        self.assert_valid_probe_still_works()

    def test_huge_input_and_division_by_zero_return_json_errors(self) -> None:
        huge_status, huge_body = self.post_calculate(
            {
                "operands": ["0", "99999999999999999999999", "1", "0"],
                "operations": ["+", "*", "+"],
                "rounding": "math",
            }
        )
        self.assertEqual(huge_status, 400)
        self.assertFalse(huge_body["ok"])
        self.assertIn("Переполнение", huge_body["error"])

        zero_status, zero_body = self.post_calculate(
            {
                "operands": ["0", "10", "0", "0"],
                "operations": ["+", "/", "+"],
                "rounding": "math",
            }
        )
        self.assertEqual(zero_status, 400)
        self.assertFalse(zero_body["ok"])
        self.assertIn("Деление на 0", zero_body["error"])

    def test_stress_api_returns_json_for_100_plus_valid_and_invalid_requests(self) -> None:
        cases: list[object] = [
            {"operands": ["0", "99999999999", "99999999999", "0"], "operations": ["+", "*", "+"], "rounding": "math"},
            {
                "operands": ["0", "99999999999999999999999", "999999999999999999999999999", "0"],
                "operations": ["+", "*", "+"],
                "rounding": "math",
            },
            {"operands": ["0", "10", "0", "0"], "operations": ["+", "/", "+"], "rounding": "math"},
            {"operands": ["1000000000000", "0.0000000001", "0", "0"], "operations": ["+", "+", "+"], "rounding": "math"},
            {"operands": ["2", "3", "4", "5"], "operations": ["+", "*", "*"], "rounding": "math"},
            {"operands": ["0", "2.5", "0", "0"], "operations": ["+", "+", "+"], "rounding": "bank"},
            {"operands": ["0", "-2.9", "0", "0"], "operations": ["+", "+", "+"], "rounding": "truncate"},
            {"operands": ["1", "2", "3"], "operations": ["+", "+", "+"], "rounding": "math"},
            {"operands": ["1", "2", "3", "4"], "operations": ["+", "+"], "rounding": "math"},
            {"operands": ["1", "2", "3", "4"], "operations": ["+", "%", "+"], "rounding": "math"},
            {"operands": ["1", "2", "3", "4"], "operations": ["+", "+", "+"], "rounding": "wrong"},
            {"left": "99999999999", "right": "99999999999", "operation": "*"},
            {"left": "1,5", "right": "2.25", "operation": "+"},
            {"left": "10", "right": "0", "operation": "/"},
            {"left": "12a3", "right": "1", "operation": "+"},
            [],
            123,
            None,
            "not an object",
            {"operands": None, "operations": ["+", "+", "+"], "rounding": "math"},
            {"operands": "1 2 3 4", "operations": ["+", "+", "+"], "rounding": "math"},
            {"operands": ["1", "2", "3", "4"], "operations": None, "rounding": "math"},
            {"operands": ["1", "2", "3", "4"], "operations": "+++", "rounding": "math"},
        ]

        valid_values = [
            "0",
            "1",
            "-1",
            "2.5",
            "-2.5",
            "1,5",
            "1 234 567,89",
            "999999999999.9999999999",
            "-999999999999.9999999999",
            "1000000000000.0000000000",
            "-1000000000000.0000000000",
            "0.0000000001",
            "-0.0000000001",
        ]
        invalid_values = [
            "",
            "abc",
            "12a3",
            "0.0-1",
            "1  23 5.67",
            "12 34.56",
            "1,2,3",
            "123e+2",
            "1.12345678901",
            "99999999999999999999999",
            "-99999999999999999999999",
        ]
        operations = ["+", "-", "*", "/", "%"]
        roundings = ["math", "bank", "truncate", "wrong"]

        for index, value in enumerate(invalid_values):
            cases.append(
                {
                    "operands": ["0", value, valid_values[index % len(valid_values)], "0"],
                    "operations": ["+", operations[index % len(operations)], "+"],
                    "rounding": "math",
                }
            )

        for index in range(90):
            values = valid_values + invalid_values
            cases.append(
                {
                    "operands": [
                        values[index % len(values)],
                        values[(index * 3 + 1) % len(values)],
                        values[(index * 5 + 2) % len(values)],
                        values[(index * 7 + 3) % len(values)],
                    ],
                    "operations": [
                        operations[index % len(operations)],
                        operations[(index + 1) % len(operations)],
                        operations[(index + 2) % len(operations)],
                    ],
                    "rounding": roundings[index % len(roundings)],
                }
            )

        self.assertGreaterEqual(len(cases), 100)
        status_counts = {200: 0, 400: 0}

        for index, payload in enumerate(cases):
            with self.subTest(index=index, payload=payload):
                status, body = self.post_calculate(payload)
                self.assertIn(status, {200, 400})
                self.assertIs(body["ok"], status == 200)
                if status == 200:
                    self.assertIn("result", body)
                    if isinstance(payload, dict) and "operands" in payload:
                        self.assertIn("rounded", body)
                else:
                    self.assertIn("error", body)
                status_counts[status] += 1

            if index % 10 == 0:
                self.assert_valid_probe_still_works()

        self.assertGreater(status_counts[200], 0)
        self.assertGreater(status_counts[400], 0)

    def test_malformed_json_returns_json_error_without_disconnect(self) -> None:
        malformed_bodies = [
            b"",
            b"{",
            b'{"operands": [1, 2, 3, 4], "operations": [',
            b"\xff\xfe",
            json.dumps(["not", "a", "dict"]).encode("utf-8"),
            json.dumps(123).encode("utf-8"),
        ]

        for index, body in enumerate(malformed_bodies):
            with self.subTest(index=index, body=body):
                status, response = self.post_raw(body)
                self.assertEqual(status, 400)
                self.assertFalse(response["ok"])
                self.assertIn("error", response)

        self.assert_valid_probe_still_works()

    def test_common_user_input_patterns_do_not_break_web_api(self) -> None:
        values = [
            "0",
            "-0",
            "+0",
            "1",
            "-1",
            "+1",
            "1.0",
            "1,0",
            ".5",
            ",5",
            "-.5",
            "-,5",
            "000001",
            "000001.2300",
            "1.",
            "1,",
            "999999999999",
            "999999999999.9999999999",
            "1000000000000",
            "1000000000000.0000000000",
            "1000000000000.0000000001",
            "-999999999999",
            "-999999999999.9999999999",
            "-1000000000000",
            "-1000000000000.0000000000",
            "-1000000000000.0000000001",
            "0.0000000001",
            "-0.0000000001",
            "0.00000000001",
            "1.1234567890",
            "1.12345678901",
            "1 000",
            "12 345",
            "123 456",
            "1 234 567",
            "1 234 567.89",
            "1 234 567,89",
            "1 234 567 890 123",
            "1234",
            "1234 567",
            "1 23 456",
            "1 2345",
            "1  234",
            "1\t234",
            "1\n234",
            " 1",
            "1 ",
            " 1 ",
            "",
            " ",
            "\t",
            "\n",
            "+",
            "-",
            ".",
            ",",
            "+.",
            "-,",
            "--1",
            "++1",
            "+-1",
            "-+1",
            "1-",
            "1+",
            "0.0-1",
            "1..2",
            "1,,2",
            "1.,2",
            "1,.2",
            "1.2.3",
            "1,2,3",
            "abc",
            "12a3",
            "one",
            "NaN",
            "Infinity",
            "-Infinity",
            "inf",
            "1e2",
            "1E2",
            "1e+309",
            "1e-309",
            "0x10",
            "0b10",
            "1/2",
            "1_000",
            "$100",
            "100%",
            "1,000.00",
            "1.000,00",
            "1 000,0000000001",
            "1 000,00000000001",
            "99999999999999999999999",
            "-99999999999999999999999",
            "9" * 80,
            "-" + "9" * 80,
            "9" * 400,
            "-" + "9" * 400,
            "0." + "0" * 200 + "1",
            "1." + "9" * 200,
            "1,2345678901",
            "1,23456789012",
            "１",
            "１２３",
            "−1",
            "—1",
            "1\u00a0234",
            "1\u00a0\u00a0234",
            "1\u202f234",
            "1\u2009234",
            "0000000000000000000000000000000",
            "0000000000000000000000000000001",
            "-0000000000000000000000000000001",
        ]

        self.assertGreaterEqual(len(values), 100)

        status_counts = {200: 0, 400: 0}
        for index, value in enumerate(values):
            with self.subTest(index=index, value=value):
                status, body = self.post_calculate(
                    {
                        "operands": ["0", value, "1", "0"],
                        "operations": ["+", "*", "+"],
                        "rounding": "math",
                    }
                )
                self.assertIn(status, {200, 400})
                self.assertIs(body["ok"], status == 200)
                self.assertIn("result" if status == 200 else "error", body)
                status_counts[status] += 1

            if index % 10 == 0:
                self.assert_valid_probe_still_works()

        self.assertGreater(status_counts[200], 0)
        self.assertGreater(status_counts[400], 0)


if __name__ == "__main__":
    unittest.main()
