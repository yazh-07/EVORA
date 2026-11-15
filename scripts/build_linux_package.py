"""Create a relocatable Linux installation and its byte-range update assets."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_incremental import write_package
from backend.incremental import LINUX_MANIFEST,INSTALLED
from backend.version import APP_VERSION


def build(backend,desktop,helper,output,version=APP_VERSION):
    backend=Path(backend).resolve();output=Path(output);package=output/'linux/evora'
    if package.exists():raise ValueError('Use an empty Linux packaging destination.')
    # PyInstaller creates shared-library links. Materialize only links pointing
    # inside the frozen bundle, so updates never follow links in installations.
    for path in backend.rglob('*'):
        if path.is_symlink() and (not path.resolve().is_relative_to(backend) or not path.resolve().is_file()):
            raise ValueError('Frozen bundle contains an external or directory link.')
    package.mkdir(parents=True)
    shutil.copytree(backend,package/'backend',symlinks=False)
    root=Path(__file__).resolve().parents[1]
    for source,name in [(desktop,'evora'),(helper,'evora-updater'),(root/'desktop/icon.png','icon.png'),
        (root/'installer/install-linux.sh','install.sh'),(root/'installer/uninstall-linux.sh','uninstall.sh')]:
        shutil.copyfile(source,package/name)
        (package/name).chmod(0o644 if name=='icon.png' else 0o755)
    sources={path.relative_to(package).as_posix():path for path in package.rglob('*') if path.is_file()}
    # Archive and incremental files have identical executable permissions.
    for path in sources.values():path.chmod(0o755 if path.stat().st_mode & 0o111 else 0o644)
    body=write_package(sources,output,version,'linux-x64')
    shutil.copyfile(output/LINUX_MANIFEST,package/INSTALLED)
    return package,body


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',default='dist/evora')
    parser.add_argument('--desktop',default='desktop/evora-linux')
    parser.add_argument('--helper',default='desktop/evora-updater')
    parser.add_argument('--output',default='dist')
    parser.add_argument('--version',default=APP_VERSION)
    args=parser.parse_args();build(args.backend,args.desktop,args.helper,args.output,args.version)
