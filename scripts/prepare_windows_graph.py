"""Build-time only: pin, verify and bundle Java/Neo4j and corresponding sources."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULES = (
    'java.se', 'jdk.unsupported', 'jdk.crypto.ec', 'jdk.crypto.cryptoki',
    'jdk.management', 'jdk.management.agent', 'jdk.jfr', 'jdk.zipfs',
    'jdk.naming.dns', 'jdk.naming.rmi', 'jdk.localedata', 'jdk.charsets',
    'jdk.nio.mapmode', 'jdk.incubator.vector', 'jdk.security.auth',
    'jdk.security.jgss', 'jdk.attach',
)


def link_runtime(jdk, output, *, linker=None):
    """Keep Java SE/services for Neo4j, excluding compiler and development tools."""
    linker = linker or (str(jdk / 'bin/jlink.exe') if os.name == 'nt' else shutil.which('jlink'))
    if not linker:
        raise RuntimeError('Java 21 jlink required to build the private runtime')
    modules = list(RUNTIME_MODULES)
    if (jdk / 'jmods/jdk.crypto.mscapi.jmod').exists():
        modules.append('jdk.crypto.mscapi')
    subprocess.run([linker, '--module-path', str(jdk / 'jmods'),
                    '--add-modules', ','.join(modules), '--strip-debug', '--compress=2',
                    '--no-man-pages', '--no-header-files', '--output', str(output)], check=True, timeout=180)
    # jlink retains per-module legal notices. Retain the upstream top-level notice too.
    for name in ('NOTICE', 'LICENSE'):
        if (jdk / name).is_file():
            shutil.copyfile(jdk / name, output / name)
    return modules


def trim_neo4j(home):
    # HTTP is disabled; EVORA uses its own UI and the Java entry points in lib/.
    for name in ('web', 'labs', 'bin', 'products', 'import', 'plugins'):
        shutil.rmtree(home / name, ignore_errors=True)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(artifact, cache):
    path = cache / artifact['sha256']
    if not path.is_file() or digest(path) != artifact['sha256']:
        temporary = path.with_suffix('.partial')
        try:
            with urlopen(Request(artifact['url'], headers={'User-Agent': 'EVORA-runtime-builder/1'}), timeout=120) as response, temporary.open('wb') as target:
                shutil.copyfileobj(response, target)
            if digest(temporary) != artifact['sha256']:
                raise ValueError('Graph runtime artifact checksum mismatch')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return path


def unpack(archive, destination):
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            name = item.filename.replace('\\', '/')
            parts = Path(name).parts
            if not parts or name.startswith('/') or ':' in name or '..' in parts or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Unsafe runtime archive path')
        zipped.extractall(destination)
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError('Unexpected runtime archive structure')
    return roots[0]


def prepare(output=None):
    output = Path(output or ROOT / 'build/windows-graph').resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = json.loads((ROOT / 'desktop/graph/runtime-lock.json').read_text())
    cache = ROOT / 'build/graph-downloads'
    cache.mkdir(parents=True, exist_ok=True)
    artifacts = {key: download(value, cache) for key, value in lock.items() if key != 'version'}
    with TemporaryDirectory(prefix='graph-stage-', dir=output.parent) as directory:
        stage = Path(directory)
        runtime = stage / 'runtime'
        runtime.mkdir()
        for key in ('neo4j', 'java'):
            unpack(artifacts[key], stage / key).rename(runtime / key)
        classes = runtime / 'classes'
        classes.mkdir()
        compiler = str(runtime / 'java/bin/javac.exe') if os.name == 'nt' else shutil.which('javac')
        if not compiler:
            raise RuntimeError('Java 21 compiler required for cross-platform staging')
        subprocess.run([compiler, '-proc:none', '--release', '21',
                        '-cp', str(runtime / 'neo4j/lib/*'), '-d', str(classes),
                        str(ROOT / 'desktop/graph/GraphHost.java')], check=True, timeout=120)
        modules = link_runtime(runtime / 'java', stage / 'linked-java')
        shutil.rmtree(runtime / 'java')
        shutil.move(str(stage / 'linked-java'), str(runtime / 'java'))
        trim_neo4j(runtime / 'neo4j')
        (runtime / 'runtime-image.json').write_text(json.dumps({
            'modules': modules, 'compiler_bundled': False,
            'neo4j_browser_bundled': False, 'compression': 'jlink-2',
        }, indent=2))
        sources = runtime / 'sources'
        sources.mkdir()
        for key in ('neo4j-source', 'java-source'):
            shutil.copyfile(artifacts[key], sources / (key + '.tar.gz'))
        shutil.copyfile(ROOT / 'desktop/graph/GraphHost.java', sources / 'GraphHost.java')
        (runtime / 'runtime-lock.json').write_text(json.dumps(lock, indent=2))
        (runtime / 'SOURCE-NOTICES.txt').write_text(
            'Neo4j Community 5.26.30 and Eclipse Temurin OpenJDK 21.0.13+9.\n'
            'Original license and legal files are retained in neo4j/ and java/.\n'
            'Corresponding upstream source archives are included in sources/.\n'
            'Pinned upstream URLs and SHA-256 values are in runtime-lock.json.\n')
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(runtime), str(output))
    return output


if __name__ == '__main__':
    print(prepare())
