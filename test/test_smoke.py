from functools import wraps
from unittest import TestCase
from pathlib import Path
import os
import json
import urllib
import zipfile
from it_depends.dependencies import SimpleSpec, Package, Dependency, resolve, SourceRepository, resolvers, resolver_by_name

IT_DEPENDS_DIR: Path = Path(__file__).absolute().parent.parent
TESTS_DIR: Path = Path(__file__).absolute().parent
REPOS_FOLDER = TESTS_DIR / "repos"


class TestResolvers(TestCase):
    maxDiff = None

    def test_resolvers(self):
        """We see all known resolvers
        caveat: Iff an unknown resolver was defined by another test it will appear here
        """
        resolver_names = {resolver.name for resolver in resolvers()}
        self.assertSetEqual(resolver_names, {'cargo', 'ubuntu', 'autotools', 'go', 'cmake', 'npm', 'pip'})
        self.assertSetEqual(resolvers(), {resolver_by_name(name) for name in resolver_names})

    def test_objects(self):
        # To/From string for nicer output and ergonomics
        self.assertEqual(str(Dependency.from_string("pip:cvedb@*")), "pip:cvedb@*")
        self.assertEqual(str(Package.from_string("pip:cvedb@0.0.1")), "pip:cvedb@0.0.1")

        # Basic Dependency object handling
        dep = Dependency.from_string("pip:cvedb@*")
        self.assertEqual(dep.source, "pip")
        self.assertEqual(dep.package, "cvedb")
        self.assertTrue(dep.semantic_version == SimpleSpec("*"))
        self.assertTrue(Dependency(source="pip", package="cvedb", semantic_version=SimpleSpec("*")) ==
                                    dep)

        # Dependency match
        solution = Package(source="pip", name="cvedb", version="0.0.1")
        self.assertTrue(dep.match(solution))
        dep2 = Dependency.from_string("pip:cvedb@<0.2.1")
        self.assertTrue(dep2.match(Package.from_string("pip:cvedb@0.2.0")))
        self.assertFalse(dep2.match(Package.from_string("pip:cvedb@0.2.1")))

    def _test_resolver(self, resolver, dep):
        dep = Dependency.from_string(dep)
        resolver = resolver_by_name(resolver)
        self.assertIs(dep.resolver, resolver)

        solutions = tuple(resolver.resolve(dep))
        self.assertGreater(len(solutions), 0)
        for package in solutions:
            self.assertEqual(package.source, dep.source)
            self.assertEqual(package.name, dep.package)
            self.assertTrue(dep.semantic_version.match(package.version))
            self.assertTrue(dep.match(package))

    def test_pip(self):
        self._test_resolver("pip", "pip:cvedb@*")

    def test_ubuntu(self):
        self._test_resolver("ubuntu", "ubuntu:libc6@*")

    def test_cargo(self):
        self._test_resolver("cargo", "cargo:rand_core@0.6.2")

    def test_npm(self):
        self._test_resolver("npm", "npm:crypto-js@4.0.0")


def gh_smoke_test(user_name, repo_name, commit):
    def smoke_test(func):
        @wraps(func)
        def wrapper(self: TestCase):
            url = f"https://github.com/{user_name}/{repo_name}/archive/{commit}.zip"
            snapshot_folder = REPOS_FOLDER / (repo_name + "-" + commit)
            snapshot_zip = snapshot_folder.with_suffix(".zip")

            if not snapshot_folder.exists():
                urllib.request.urlretrieve(url, snapshot_zip)
                with zipfile.ZipFile(snapshot_zip, "r") as zip_ref:
                    zip_ref.extractall(REPOS_FOLDER)

            expected_json = REPOS_FOLDER / f"{repo_name}.expected.json"
            actual_json = REPOS_FOLDER / f"{repo_name}.actual.json"

            package_list = resolve(SourceRepository(snapshot_folder), max_workers=1 )
            result_it_depends = package_list.to_obj()
            with open(actual_json, "w") as f:
                f.write(json.dumps(result_it_depends, indent=4, sort_keys=True))

            if not expected_json.exists():
                raise ValueError(f"File {expected_json.absolute()} needs to be created! See {actual_json.absolute()} "
                                 "for the output of the most recent run.")
            with open(expected_json, "r") as f:
                expected = json.load(f)
            if result_it_depends != expected:
                print(f"See {actual_json.absolute()} for the result of this run.")
            self.assertEqual(result_it_depends, expected)

            return func(self, package_list)

        return wrapper

    return smoke_test


class TestSmoke(TestCase):
    maxDiff = None

    def setUp(self) -> None:
        if not os.path.exists(REPOS_FOLDER):
            os.makedirs(REPOS_FOLDER)

    @gh_smoke_test("trailofbits", "cvedb", "7441dc0e238e31829891f85fd840d9e65cb629d8")
    def test_pip(self, package_list):
        pass

    @gh_smoke_test("trailofbits", "siderophile", "7bca0f5a73da98550c29032f6a2a170f472ea241")
    def test_cargo(self, package_list):
        pass

    @gh_smoke_test("brix", "crypto-js", "971c31f0c931f913d22a76ed488d9216ac04e306")
    def test_npm(self, package_list):
        pass

    @gh_smoke_test("bitcoin", "bitcoin", "4a267057617a8aa6dc9793c4d711725df5338025")
    def test_autotools(self, package_list):
        pass

    @gh_smoke_test("lifting-bits", "rellic", "9cf73b288a3d0c51d5de7e1060cba8656538596f")
    def __test_cmake(self, package_list):
        pass
