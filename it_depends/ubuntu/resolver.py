from functools import lru_cache
import shutil
import subprocess
import logging
import re
from typing import Iterable, Iterator, Optional

from .apt import file_to_packages
from .docker import is_running_ubuntu, run_command
from ..dependencies import Version, SimpleSpec
from ..dependencies import (
    Dependency, DependencyResolver, Package, PackageCache, ResolverAvailability, SourcePackage, SourceRepository
)
from ..native import get_native_dependencies

logger = logging.getLogger(__name__)


class UbuntuResolver(DependencyResolver):
    name = "ubuntu"
    description = "expands dependencies based upon Ubuntu package dependencies"

    _pattern = re.compile(r" *(?P<package>[^ ]*)( *\((?P<version>.*)\))? *")
    _ubuntu_version = re.compile("([0-9]+:)*(?P<version>[^-]*)(-.*)*")

    @staticmethod
    @lru_cache(maxsize=2048)
    def ubuntu_packages(package_name: str) -> Iterable[Package]:
        """Iterates over all of the package versions available for a package name"""
        # Parses the dependencies of dependency.package out of the `apt show` command
        logger.debug(f"Running `apt show -a {package_name}`")
        contents = run_command("apt", "show", "-a", package_name).decode("utf8")

        # Possibly means that the package does not appear ubuntu with the exact name
        if not contents:
            logger.info(f"Package {package_name} not found in ubuntu installed apt sources")
            return ()

        # Example depends line:
        # Depends: libc6 (>= 2.29), libgcc-s1 (>= 3.4), libstdc++6 (>= 9)
        version: Optional[Version] = None
        packages = []
        for line in contents.split("\n"):
            if line.startswith("Version: "):
                matched = UbuntuResolver._ubuntu_version.match(line[len("Version: "):])
                if matched:
                    version = Version.coerce(matched.group("version"))
                else:
                    logger.warning(f"Failed to parse package {package_name} {line}")
            elif version is not None and line.startswith("Depends: "):
                deps = []
                for dep in line[9:].split(","):
                    matched = UbuntuResolver._pattern.match(dep)
                    if not matched:
                        raise ValueError(f"Invalid dependency line in apt output for {package_name}: {line!r}")
                    dep_package = matched.group('package')
                    dep_version = matched.group('version')
                    try:
                        dep_version = dep_version.replace(" ", "")
                        SimpleSpec(dep_version.replace(" ", ""))
                    except Exception as e:
                        print ("EXCEPTION trying to parse", dep, "setting to *", e)
                        dep_version = "*"  # Yolo FIXME Invalid simple block '= 1:7.0.1-12'

                    deps.append((dep_package, dep_version))

                packages.append(Package(
                    name=package_name, version=version,
                    source=UbuntuResolver(),
                    dependencies=(
                        Dependency(
                            package=pkg,
                            semantic_version=SimpleSpec(ver),
                            source=UbuntuResolver()
                        )
                        for pkg, ver in deps
                    )
                ))
                version = None
        return packages

    def resolve(self, dependency: Dependency) -> Iterator[Package]:
        if dependency.source != "ubuntu":
            raise ValueError(f"{self} can not resolve dependencies from other sources ({dependency})")

        if dependency.package.startswith("/"):
            # this is a file path, likely produced from native.py
            try:
                deps = []
                for pkg_name in file_to_packages(dependency.package):
                    deps.append(Dependency(package=pkg_name, source=UbuntuResolver.name))
                if deps:
                    yield Package(
                        name=dependency.package,
                        source=dependency.source,
                        version=Version.coerce("0"),
                        dependencies=deps
                    )
            except (ValueError, subprocess.CalledProcessError):
                pass
        else:
            for package in UbuntuResolver.ubuntu_packages(dependency.package):
                if package.version in dependency.semantic_version:
                    yield package

    def __lt__(self, other):
        """Make sure that the Ubuntu Classifier runs last"""
        return False

    def is_available(self) -> ResolverAvailability:
        if not (shutil.which("apt") is not None and is_running_ubuntu()) and shutil.which("docker") is None:
            return ResolverAvailability(False,
                                        "`Ubuntu` classifier either needs to be running from Ubuntu 20.04 or "
                                        "to have Docker installed")
        return ResolverAvailability(True)

    def can_resolve_from_source(self, repo: SourceRepository) -> bool:
        return False

    def resolve_from_source(
            self, repo: SourceRepository, cache: Optional[PackageCache] = None
    ) -> Optional[SourcePackage]:
        return None

    def can_update_dependencies(self, package: Package) -> bool:
        return package.source != UbuntuResolver.name

    def update_dependencies(self, package: Package) -> Package:
        native_deps = get_native_dependencies(package)
        package.dependencies = package.dependencies.union(frozenset(native_deps))
        return package
