"""Deployment safety: the Blueprint must only create FREE resources, and the photo downloader must never break a build."""
import re, unittest
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


class BlueprintIsFree(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "render.yaml").read_text()
        self.cfg = yaml.safe_load(self.text)

    def test_only_one_free_web_service(self):
        self.assertEqual(set(self.cfg) - {"services"}, set(), "no databases / keyvalue / envVarGroups / previews / paid top-level resources")
        svcs = self.cfg["services"]
        self.assertEqual(len(svcs), 1)
        s = svcs[0]
        self.assertEqual(s["type"], "web"); self.assertEqual(s["plan"], "free")
        for forbidden in ("disk", "disks", "numInstances", "scaling", "autoscaling", "maxShutdownDelaySeconds"):
            self.assertNotIn(forbidden, s, forbidden)

    def test_no_paid_keywords_anywhere(self):
        code = "\n".join(re.sub(r"\s#.*$", "", l) for l in self.text.splitlines() if not l.strip().startswith("#"))
        for word in ("starter", "standard", "pro", "plus", "pserv", "worker", "cron", "redis", "keyvalue", "postgres", "databases", "disk:"):
            self.assertIsNone(re.search(rf"\b{re.escape(word)}\b", code), word)

    def test_start_and_build_commands(self):
        s = self.cfg["services"][0]
        self.assertIn("gunicorn app:app", s["startCommand"]); self.assertIn("$PORT", s["startCommand"])
        self.assertEqual(s["buildCommand"].strip(), "pip install -r requirements.txt")                           # nothing else runs at build time
        keys = {e["key"]: e for e in s["envVars"]}
        self.assertTrue(keys["SECRET_KEY"].get("generateValue")); self.assertTrue(keys["GEMINI_API_KEY"].get("sync") is False)
        self.assertNotIn("value", keys["GEMINI_API_KEY"])                                                       # no secret committed

    def test_requirements_complete(self):
        req = (ROOT / "requirements.txt").read_text().lower()
        for pkg in ("flask", "gunicorn", "openpyxl", "requests"):
            self.assertIn(pkg, req)


class PhotosShipped(unittest.TestCase):
    def test_eight_real_photos_are_bundled(self):
        for i in range(1, 9):
            f = ROOT / "static" / "img" / "scenes" / f"{i}.jpg"
            self.assertTrue(f.exists(), f)
            im = Image.open(f); self.assertEqual(im.format, "JPEG"); self.assertGreaterEqual(im.size[0], 800); self.assertGreater(im.size[0], im.size[1])
            self.assertLess(f.stat().st_size, 400_000)                                                         # keeps the repo and page weight small

    def test_no_external_image_or_build_dependency(self):
        for js in (ROOT / "static" / "js").glob("*.js"):
            self.assertNotIn("wikimedia", js.read_text().lower(), js.name)
        self.assertFalse((ROOT / "tools").exists())


if __name__ == "__main__":
    unittest.main()
