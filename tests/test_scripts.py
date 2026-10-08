"""Regression and security tests for the evm-dd scripts. Run: python3 -m unittest discover -s tests -v"""
import json, os, re, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
EXAMPLE = os.path.join(ROOT, "examples", "fictional-protocol")
sys.path.insert(0, SCRIPTS)
import ddlib  # noqa: E402


def run(script, *args, env=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args], capture_output=True, text=True, env=e, timeout=180)


class TempProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.proj = os.path.join(self.tmp, "fictional-protocol")
        shutil.copytree(EXAMPLE, self.proj, ignore=shutil.ignore_patterns("site"))
        self.env = {"EVM_DD_HOME": os.path.join(self.tmp, "ws")}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def sc(self):
        with open(os.path.join(self.proj, "scorecard.json"), encoding="utf-8") as f: return json.load(f)

    def save(self, sc):
        with open(os.path.join(self.proj, "scorecard.json"), "w", encoding="utf-8") as f: json.dump(sc, f)

    def page(self):
        with open(os.path.join(self.proj, "site", "fictional-protocol.html"), encoding="utf-8") as f: return f.read()


class TestExample(TempProject):
    def test_build_and_check_pass(self):
        r = run("build.py", self.proj, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        html = self.page()
        self.assertIn("<!doctype html>", html)
        self.assertIn('name="viewport"', html)
        self.assertIn('<div id="view-report" hidden>', html)
        r = run("check.py", self.proj, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @unittest.skipUnless(shutil.which("google-chrome") or shutil.which("chromium") or os.path.exists("/Applications/Google Chrome.app"), "Chrome not installed")
    def test_pdf_is_one_page(self):
        r = run("build.py", self.proj, "--pdf", env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("(1 page)", r.stdout)

    def test_bad_mean_is_caught(self):
        sc = self.sc(); sc["final_rating"] = 9.9; self.save(sc)
        self.assertNotEqual(run("build.py", self.proj, env=self.env).returncode, 0)
        self.assertNotEqual(run("check.py", self.proj, env=self.env).returncode, 0)


class TestHtmlInjection(TempProject):
    def test_script_and_js_links_are_neutralised(self):
        sc = self.sc()
        evil = '<script>alert(1)</script><img src=x onerror=alert(2)>'
        sc["project"] = "Acme " + evil
        op = sc["onepager"]
        op["tagline"] = 'See [click](javascript:alert(3)) and "quotes" ' + evil
        op["tldr"] = op["tldr"] + ' [x](https://ok.example/"onmouseover="alert(4))'
        op["links"] = [["Bad", "javascript:alert(5)"], ["Data", "data:text/html,<script>alert(6)</script>"], ["Good", "https://acme-vaults.example"]]
        op["kpis"][0][0] = evil
        sc["categories"][0]["rationale"] = evil
        self.save(sc)
        with open(os.path.join(self.proj, "report.md"), "a", encoding="utf-8") as f:
            f.write("\n\n" + evil + " [link](javascript:alert(7))\n")
        r = run("build.py", self.proj, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        html = self.page()
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("<img src=x", html)
        self.assertIsNone(re.search(r"(href|src|action)\s*=\s*[\"']?\s*(javascript|data|vbscript):", html, re.I))
        self.assertNotIn('"onmouseover="', html)
        self.assertIn('href="https://acme-vaults.example"', html)
        self.assertNotEqual(run("check.py", self.proj, env=self.env).returncode, 0, "check.py must flag non-http links")

    def test_logo_path_traversal_rejected(self):
        sc = self.sc(); sc["onepager"]["logo"] = "../../scorecard.json"; self.save(sc)
        r = run("build.py", self.proj, env=self.env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("invalid asset file name", r.stderr)


class TestNewProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); self.ws = os.path.join(self.tmp, "ws"); os.makedirs(self.ws)
        self.env = {"EVM_DD_HOME": self.ws}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_scaffold(self):
        r = run("new_project.py", "acme", "Acme", "https://acme.example", "--link", "Docs=https://docs.acme.example", env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.ws, "projects", "acme", "scorecard.json")) as f: sc = json.load(f)
        self.assertEqual(sc["project"], "Acme")

    def test_quotes_in_name_keep_json_valid(self):
        r = run("new_project.py", "quoted", 'Acme "Quoted" \\ Name', "https://acme.example", env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.ws, "projects", "quoted", "scorecard.json")) as f: json.load(f)

    def test_rejects_traversal_and_bad_urls(self):
        for args in (["../evil", "X", "https://x.example"], ["UPPER", "X", "https://x.example"], ["ok", "X", "javascript:alert(1)"],
                     ["ok2", "X", "https://x.example", "--link", "Docs=file:///etc/passwd"], ["ok3", "<b>X</b>", "https://x.example"]):
            r = run("new_project.py", *args, env=self.env)
            self.assertNotEqual(r.returncode, 0, args)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil")))
        self.assertFalse(os.path.exists(os.path.join(self.ws, "projects", "ok")))

    def test_refuses_missing_workspace(self):
        r = run("new_project.py", "acme", "Acme", "https://acme.example", env={"EVM_DD_HOME": os.path.join(self.tmp, "nope")})
        self.assertNotEqual(r.returncode, 0)


class TestValidators(unittest.TestCase):
    def test_slug(self):
        for ok in ("a", "acme-vaults", "x1"):
            ddlib.check_slug(ok)
        for bad in ("", "../x", "A", "-x", "a/b", "a" * 65, "a b"):
            with self.assertRaises(ValueError): ddlib.check_slug(bad)

    def test_handle(self):
        self.assertEqual(ddlib.check_handle("@Acme_1"), "Acme_1")
        for bad in ("../x", "a" * 16, "a b", "a?b=1", ""):
            with self.assertRaises(ValueError): ddlib.check_handle(bad)

    def test_safe_url(self):
        self.assertEqual(ddlib.safe_url("https://a.example/x?y=1"), "https://a.example/x?y=1")
        for bad in ("javascript:alert(1)", "JAVASCRIPT:alert(1)", "data:text/html,x", "//a.example", "/rel", "https://", 'https://a.example/"x', "https://a.example/<x>", None, 5):
            self.assertIsNone(ddlib.safe_url(bad), bad)

    def test_x_scripts_reject_bad_input_before_network(self):
        self.assertNotEqual(run("x_reach.py", "../../etc").returncode, 0)
        self.assertNotEqual(run("x_reach.py", "ok", "--since", "yesterday").returncode, 0)
        r = run("x_sentiment.py", "--project", "../x", "--handle", "ok", "--terms", "t", "--today", "2026-10-08", env={"XAI_API_KEY": "test-not-a-key"})
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("test-not-a-key", r.stdout + r.stderr)
        r = run("x_metrics.py", "--project", "ok", "--handle", "a/b", "--today", "2026-10-08")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
