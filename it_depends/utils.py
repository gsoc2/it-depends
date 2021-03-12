import functools
import os
import re
import logging
import subprocess
import gzip

logger = logging.getLogger(__name__)

popdb = {}
@functools.lru_cache(maxsize=128)
def _popularity(packagename):
    """
    Downloads and uses popularity database
    """

    if arch not in ("amd64", "i386"):
        raise ValueError("Only amd64 and i386 supported")
    selected = None

    if not popdb:
        # TODO find better location https://pypi.org/project/appdirs/?

        dbfile = os.path.join(os.path.dirname(__file__), f"popcount.gz")
        if not os.path.exists(dbfile):
            logger.info("Popularity db not found. Downloading.")
            urllib.request.urlretrieve(
                "https://popcon.ubuntu.com/by_inst.gz",
                dbfile)

        logger.info("Popularity memory index not found. Building.")
        with gzip.open(dbfile, "rt") as contents:
            for line in contents.readlines():
                if line.startswith("#"):
                    continue
                print (line)
                re.compile(r"(?P<name>\S+)\s+")
                line.split(" ")
    print ("AAAAAAAAAAAAHH!")
    return 0

all_packages = None
def get_apt_packages():
    global all_packages
    if all_packages is None:
        logger.info("Rebuilding global apt package list.")
        all_packages = subprocess.check_output(["apt", "list"]).decode("utf8")
        all_packages = tuple(map(lambda x: x.split("/")[0], all_packages.splitlines()))
        logger.info(f"Global apt package count {len(all_packages)}")
    return all_packages


contents_db = {}
@functools.lru_cache(maxsize=128)
def _file_to_package_contents(filename, arch="amd64"):
    """
    Downloads and uses apt-file database directly
    # http://security.ubuntu.com/ubuntu/dists/focal-security/Contents-amd64.gz
    # http://security.ubuntu.com/ubuntu/dists/focal-security/Contents-i386.gz
    """
    print ( f"_file_to_package_contents({filename}, {arch})")
    if arch not in ("amd64", "i386"):
        raise ValueError("Only amd64 and i386 supported")
    selected = None

    # TODO find better location https://pypi.org/project/appdirs/?
    dbfile = os.path.join(os.path.dirname(__file__), f"Contents-{arch}.gz")
    if not os.path.exists(dbfile):
        urllib.request.urlretrieve(
            f"http://security.ubuntu.com/ubuntu/dists/focal-security/Contents-{arch}.gz",
            dbfile)
    if not contents_db:
        logger.inf("Rebuilding contents db")
        with gzip.open(dbfile, "rt") as contents:
            for line in contents.readlines():
                filename_i, *packages_i = re.split(r"\s+", line[:-1])
                assert(len(packages_i)>0)
                contents_db.setdefault(filename_i, []).extend(packages_i)

    regex = re.compile("(.*/)+"+filename+"$")
    matches = 0
    for (filename_i, packages_i) in contents_db.items():
        if regex.match(filename_i):
            matches += 1
            for package_i in packages_i:
                if selected is None or len(selected[0]) > len(filename_i):
                    selected = filename_i, package_i
    import pdb; pdb.set_trace()
    if selected:
        logger.info(
            f"Found {matches} matching packages for {filename}. Choosing {selected[1]}")
    else:
        raise ValueError(f"{filename} not found in Contents database")
    return selected[1]

@functools.lru_cache(maxsize=128)
def _file_to_package_apt_file(filename, arch="amd64"):
    if arch not in ("amd64", "i386"):
        raise ValueError("Only amd64 and i386 supported")
    logger.info(f'Running [{" ".join(["apt-file", "-x", "search", filename])}]')
    contents = subprocess.run(["apt-file", "-x", "search", filename],
                              stdout=subprocess.PIPE).stdout.decode("utf8")
    db = {}
    selected = None
    for line in contents.split("\n"):
        if not line:
            continue
        package_i, filename_i = line.split(": ")
        db[filename_i] = package_i
        if selected is None or len(selected[0]) > len(filename_i):
            selected = filename_i, package_i

    if selected:
        logger.info(
            f"Found {len(db)} matching packages for {filename}. Choosing {selected[1]}")
    else:
        raise ValueError(f"{filename} not found in apt-file")

    return selected[1]

@functools.lru_cache(maxsize=128)
def file_to_package(filename, arch="amd64"):
    filename = f"/{filename}$"
    return _file_to_package_apt_file(filename, arch=arch)
    return _file_to_package_contents(filename, arch=arch)
