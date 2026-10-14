"""生成带标准 HA 安装路径的白名单 ZIP，并核对包内容。"""
import hashlib
import logging
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from validate_release import ROOT, RUNTIME, validate

LOGGER = logging.getLogger(__name__)


def build():
    """验证后仅打包运行文件、文档和许可证，校验解压内容一致。"""
    validate()
    names = {f'custom_components/konke_local/{name}' for name in RUNTIME} | {'README.md', 'LICENSE', 'CHANGELOG.md'}
    target = ROOT / 'dist/home-assistant-konke-v0.1.0.zip'
    target.parent.mkdir(exist_ok=True)
    with ZipFile(target, 'w', ZIP_DEFLATED) as archive:
        for name in sorted(names):
            archive.write(ROOT / name, name)
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == names
        for name in names:
            assert archive.read(name) == (ROOT / name).read_bytes()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n', encoding='utf-8')
    print(f'Package verified: {target.name}, {len(names)} files, SHA256 {digest}')


if __name__ == '__main__':
    try:
        build()
    except Exception:
        LOGGER.exception('Package build failed')
        raise
