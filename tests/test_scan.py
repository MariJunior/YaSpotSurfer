from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from yandex_spike.application.scan import (
    ScanError,
    clear_user_library_data,
    scan_user_library,
    user_snapshot_path,
)
from yandex_spike.telegram.copy import scan_done_text


class ScanUseCaseTests(unittest.TestCase):
    def test_requires_yandex_token(self) -> None:
        store = MagicMock()
        store.read_yandex_token.return_value = None
        with self.assertRaises(ScanError) as ctx:
            scan_user_library(store, 42)
        self.assertIn("connect_yandex", str(ctx.exception))

    @patch("yandex_spike.application.scan.inspect_library")
    def test_writes_per_user_snapshot(self, inspect_mock) -> None:
        inspect_mock.return_value = {
            "liked_tracks_count": 10,
            "playlists_count": 2,
            "isrc": {"liked_tracks_with_isrc": 0},
        }
        store = MagicMock()
        store.read_yandex_token.return_value = "tok"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = scan_user_library(store, 7, data_root=root)
            self.assertEqual(result.liked_tracks_count, 10)
            self.assertEqual(result.playlists_count, 2)
            expected = user_snapshot_path(7, root=root)
            kwargs = inspect_mock.call_args.kwargs
            self.assertEqual(kwargs["access_token"], "tok")
            self.assertEqual(kwargs["snapshot_path"], expected)
            self.assertEqual(kwargs["raw_dir"], root / "7" / "raw")

    def test_clear_user_library_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lib = root / "99" / "raw"
            lib.mkdir(parents=True)
            (lib / "x.json").write_text("{}", encoding="utf-8")
            clear_user_library_data(99, root=root)
            self.assertFalse((root / "99").exists())

    def test_scan_done_copy(self) -> None:
        text = scan_done_text(liked_tracks=3996, playlists=51, liked_with_isrc=0)
        self.assertIn("3996", text)
        self.assertIn("51", text)
        self.assertIn("названию", text)


if __name__ == "__main__":
    unittest.main()
