"""Позитивні та негативні синтетичні тести контролю URL свідків."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_witness_urls.py"
spec = importlib.util.spec_from_file_location("audit_witness_urls", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GRETIL = "https://www.gretil.uni-goettingen.de/gretil/corpustei/transformations/html/sa_aSTAvakragItA.htm"
TEXTGRID = "https://www.textgridrep.org/browse/49ks7.0"
MIRROR = "https://tylergneill.github.io/gretil-mirror/gretil/corpustei/transformations/html/sa_aSTAvakragItA.htm"
GITHUB_MIRROR = "https://raw.githubusercontent.com/INDOLOGY/GRETIL-mirror/main/gretil.sub.uni-goettingen.de/gretil/corpustei/sa_aSTAvakragItA.xml"
SARIT = "https://github.com/sarit/SARIT-corpus/blob/master/astavakragita.xml"
SARIT_PINNED = "https://github.com/sarit/SARIT-corpus/blob/0fbf1f2385b5e3331dd8dd625cab4b37c6d73103/astavakragita.xml"


class WitnessUrlsTests(unittest.TestCase):
    def test_official_gretil(self):
        self.assertEqual(module.inspect_url("gretil", GRETIL), (None, []))

    def test_textgrid_warning(self):
        error, notes = module.inspect_url("gretil", TEXTGRID)
        self.assertIsNone(error)
        self.assertTrue(notes)

    def test_unverified_mirror_warning(self):
        error, notes = module.inspect_url("gretil", MIRROR)
        self.assertIsNone(error)
        self.assertIn("дзеркало", notes[0])

    def test_archive_mirror_warns_twice(self):
        error, notes = module.inspect_url("gretil", GITHUB_MIRROR)
        self.assertIsNone(error)
        self.assertEqual(len(notes), 2)

    def test_sarit_mutable_warning(self):
        error, notes = module.inspect_url("sarit", SARIT)
        self.assertIsNone(error)
        self.assertTrue(notes)

    def test_sarit_pinned(self):
        self.assertEqual(module.inspect_url("sarit", SARIT_PINNED), (None, []))

    def test_raw_sarit(self):
        raw = SARIT_PINNED.replace("https://github.com/", "https://raw.githubusercontent.com/").replace("/blob/", "/")
        self.assertEqual(module.inspect_url("sarit", raw), (None, []))

    def test_wrong_repo(self):
        self.assertIsNotNone(module.inspect_url("sarit", SARIT.replace("/sarit/", "/attacker/"))[0])

    def test_wrong_file(self):
        self.assertIsNotNone(module.inspect_url("sarit", SARIT.replace("astavakragita.xml", "README.md"))[0])

    def test_host_spoof(self):
        self.assertIsNotNone(module.inspect_url("gretil", GRETIL.replace("gretil.uni-goettingen.de", "gretil.uni-goettingen.de.evil.example"))[0])

    def test_wrong_host(self):
        self.assertIsNotNone(module.inspect_url("sarit", "https://example.org/astavakragita.xml")[0])

    def test_http_forbidden(self):
        self.assertIsNotNone(module.inspect_url("gretil", GRETIL.replace("https:", "http:"))[0])

    def test_credentials_forbidden(self):
        self.assertIsNotNone(module.inspect_url("sarit", SARIT.replace("github.com", "sarit@github.com"))[0])

    def test_query_forbidden(self):
        self.assertIsNotNone(module.inspect_url("sarit", SARIT + "?redirect=1")[0])

    def test_fragment_forbidden(self):
        self.assertIsNotNone(module.inspect_url("sarit", SARIT + "#verse_1.2")[0])

    def test_port_forbidden(self):
        self.assertIsNotNone(module.inspect_url("sarit", SARIT.replace("github.com", "github.com:443"))[0])

    def test_unknown_witness(self):
        self.assertIsNotNone(module.inspect_url("unknown", GRETIL)[0])

    def test_missing_folder_reports_zero(self):
        with tempfile.TemporaryDirectory() as root:
            result = module.audit(Path(root) / "does-not-exist")
        self.assertEqual(result["cards"], 0)
        self.assertEqual(result["status"], "ok")

    def test_valid_cards_and_warnings(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "1.2.json").write_text(json.dumps({"sources": {
                "gretil": {"url": GRETIL}, "sarit": {"url": SARIT_PINNED}}}), encoding="utf-8")
            (folder / "1.3.json").write_text(json.dumps({"sources": {
                "gretil": {"url": MIRROR}, "sarit": {"url": SARIT}}), encoding="utf-8")
            result = module.audit(folder)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["cards"], 2)
        self.assertEqual(len(result["warnings"]), 2)

    def test_invalid_json_and_sources_fail(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "1.2.json").write_text(json.dumps({"sources": {
                "gretil": {"url": "https://example.org/"}, "sarit": {"url": SARIT}}}), encoding="utf-8")
            (folder / "1.3.json").write_text("[", encoding="utf-8")
            (folder / "1.4.json").write_text("null", encoding="utf-8")
            result = module.audit(folder)
        self.assertEqual(result["cards"], 3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["errors"]), 3)


if __name__ == "__main__":
    unittest.main()
