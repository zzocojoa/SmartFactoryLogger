import csv
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.validate_spot_image_files import inspect_image_file


class SpotImageFileValidationTests(unittest.TestCase):
    @staticmethod
    def make_copy(directory: Path) -> tuple[Path, Path, Path]:
        root = directory / "copy"
        capture = root / "spot_images"
        capture.mkdir(parents=True)
        image = capture / "recorded.jpg"
        Image.new("RGB", (8, 8), "blue").save(image)
        fact = root / "spot_image_fact.csv"
        with fact.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["spot_image_capture_id", "spot_image_path", "spot_image_sha256", "spot_image_size_bytes"])
            writer.writerow(["capture-1", "spot_images/recorded.jpg", hashlib.sha256(image.read_bytes()).hexdigest(), image.stat().st_size])
        return fact, capture, image

    def test_duplicate_fact_is_failure_and_checked_file_count_is_unique(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files

        with tempfile.TemporaryDirectory() as directory:
            fact, capture, _ = self.make_copy(Path(directory))
            lines = fact.read_text(encoding="utf-8-sig").splitlines()
            fact.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8-sig")
            result = audit_image_files(fact, capture, Path(directory) / "result")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["issue_counts"]["duplicate_capture_id_or_path"], 1)
            self.assertEqual(result["fact_row_count"], 2)
            self.assertEqual(result["checked_file_count"], 1)

    @unittest.skipUnless(os.name == "nt", "Windows path identity regression")
    def test_windows_case_alias_is_one_file_and_duplicate_reference(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files

        with tempfile.TemporaryDirectory() as directory:
            fact, capture, _ = self.make_copy(Path(directory))
            lines = fact.read_text(encoding="utf-8-sig").splitlines()
            alias = lines[1].replace("capture-1", "capture-2").replace("spot_images/recorded.jpg", "SPOT_IMAGES/RECORDED.JPG")
            fact.write_text("\n".join([*lines, alias]) + "\n", encoding="utf-8-sig")
            result = audit_image_files(fact, capture, Path(directory) / "result")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["checked_file_count"], 1)
            self.assertEqual(result["issue_counts"]["duplicate_capture_id_or_path"], 1)

    def test_audit_checks_reverse_reference_and_keeps_inputs_unchanged(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "copy"
            capture = root / "spot_images"
            capture.mkdir(parents=True)
            image = capture / "recorded.jpg"
            Image.new("RGB", (8, 8), "blue").save(image)
            orphan = capture / "orphan.jpg"
            orphan.write_bytes(image.read_bytes())
            fact = root / "spot_image_fact.csv"
            with fact.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["spot_image_capture_id", "spot_image_path", "spot_image_sha256", "spot_image_size_bytes"])
                writer.writerow(["capture-1", "spot_images/recorded.jpg", hashlib.sha256(image.read_bytes()).hexdigest(), image.stat().st_size])
            before = {str(path): path.read_bytes() for path in (fact, image, orphan)}
            result = audit_image_files(fact, capture, Path(directory) / "result")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["orphan_file_count"], 1)
            self.assertEqual(result["checked_file_count"], 2)
            self.assertEqual(result["fact_row_count"], 1)
            self.assertEqual(result["full_data_gate"], "NOT_EVALUATED")
            self.assertEqual(before, {str(path): path.read_bytes() for path in (fact, image, orphan)})

    def test_matching_hash_does_not_hide_truncated_pixels(self) -> None:
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "red").save(buffer, format="JPEG")
        payload = buffer.getvalue()[:-10]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.jpg"
            path.write_bytes(payload)
            result = inspect_image_file(path, hashlib.sha256(payload).hexdigest(), len(payload))
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("decode_failed", result["issues"])

    def test_healthy_copy_passes_only_image_scope_and_output_cannot_be_reused(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files

        with tempfile.TemporaryDirectory() as directory:
            fact, capture, _ = self.make_copy(Path(directory))
            output = Path(directory) / "result"
            result = audit_image_files(fact, capture, output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["full_data_gate"], "NOT_EVALUATED")
            self.assertEqual(result["issue_counts"], {})
            self.assertEqual(result["checked_file_count"], result["inventory_file_count"])
            self.assertEqual(json.loads((output / "summary.json").read_text()), result)
            with self.assertRaises(FileExistsError):
                audit_image_files(fact, capture, output)
            with self.assertRaisesRegex(ValueError, "outside_input_copy"):
                audit_image_files(fact, capture, capture.parent / "result")

    def test_actual_hash_and_size_are_compared_with_recorded_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, image = self.make_copy(Path(directory))
            result = inspect_image_file(image, "0" * 64, image.stat().st_size + 1)
            self.assertEqual(set(result["issues"]), {"sha256_mismatch", "size_mismatch"})
            self.assertEqual(result["status"], "FAIL")

    def test_unsafe_paths_do_not_read_outside_copy(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files, sha256_file

        for path_text in ["../outside.jpg", "/outside.jpg", "C:\\outside.jpg", "\\\\server\\share\\x.jpg", "spot_images/x.jpg:stream"]:
            with self.subTest(path=path_text), tempfile.TemporaryDirectory() as directory:
                fact, capture, _ = self.make_copy(Path(directory))
                text = fact.read_text(encoding="utf-8-sig").replace("spot_images/recorded.jpg", path_text)
                fact.write_text(text, encoding="utf-8-sig")
                with patch("scripts.validate_spot_image_files.sha256_file", wraps=sha256_file) as hashing:
                    result = audit_image_files(fact, capture, Path(directory) / "result")
                self.assertEqual(result["status"], "FAIL")
                self.assertIn("unsafe_image_path", result["issue_counts"])
                self.assertFalse(any("outside.jpg" in str(call.args[0]) for call in hashing.call_args_list))

    def test_changed_copy_is_rejected_even_if_size_and_mtime_are_restored(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files

        with tempfile.TemporaryDirectory() as directory:
            fact, capture, image = self.make_copy(Path(directory))
            before = image.stat()

            def change_after_inspection(*args):
                result = inspect_image_file(*args)
                data = bytearray(image.read_bytes())
                data[-12] ^= 1
                image.write_bytes(data)
                os.utime(image, ns=(before.st_atime_ns, before.st_mtime_ns))
                return result

            with patch("scripts.validate_spot_image_files.inspect_image_file", side_effect=change_after_inspection):
                result = audit_image_files(fact, capture, Path(directory) / "result")
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("inventory_changed", result["issue_counts"])

    def test_every_animation_frame_is_decoded(self) -> None:
        buffer = io.BytesIO()
        Image.new("RGB", (16, 16), "red").save(
            buffer, format="GIF", save_all=True,
            append_images=[Image.new("RGB", (16, 16), "blue")],
        )
        payload = buffer.getvalue()
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "two-frames.gif"
            image.write_bytes(payload)
            result = inspect_image_file(image, hashlib.sha256(payload).hexdigest(), len(payload))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["decoded_frames"], 2)

    def test_missing_image_is_failure_and_not_an_orphan(self) -> None:
        from scripts.validate_spot_image_files import audit_image_files

        with tempfile.TemporaryDirectory() as directory:
            fact, capture, image = self.make_copy(Path(directory))
            image.unlink()
            result = audit_image_files(fact, capture, Path(directory) / "result")
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["issue_counts"]["missing_file"], 1)
            self.assertEqual(result["orphan_file_count"], 0)


if __name__ == "__main__":
    unittest.main()
