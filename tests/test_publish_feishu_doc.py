from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "publish_feishu_doc.py"


def load_publish_module():
    spec = importlib.util.spec_from_file_location("publish_feishu_doc", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PublishFeishuDocTests(unittest.TestCase):
    def test_deletes_input_markdown_after_successful_publish(self) -> None:
        module = load_publish_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "study-note.md"
            markdown_path.write_text("# Study note\n", encoding="utf-8")

            argv = [
                "publish_feishu_doc.py",
                "--input",
                str(markdown_path),
                "--title",
                "Study Note",
            ]
            stdout = io.StringIO()
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(module, "publish", return_value="https://feishu.cn/docx/doc123"),
                contextlib.redirect_stdout(stdout),
            ):
                exit_code = module.main()

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue().strip(), "https://feishu.cn/docx/doc123")
            self.assertFalse(markdown_path.exists())

    def test_keeps_input_markdown_when_publish_fails(self) -> None:
        module = load_publish_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "study-note.md"
            markdown_path.write_text("# Study note\n", encoding="utf-8")

            argv = [
                "publish_feishu_doc.py",
                "--input",
                str(markdown_path),
                "--title",
                "Study Note",
            ]
            stderr = io.StringIO()
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(module, "publish", side_effect=module.FeishuError("boom")),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = module.main()

            self.assertEqual(exit_code, 1)
            self.assertTrue(markdown_path.exists())
            self.assertIn("FEISHU_PUBLISH_FAILED", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
