"""离线检查发布结构、清单、翻译和明显敏感材料，不连接设备。"""
import ast
import json
import logging
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'custom_components/konke_local'
LOGGER = logging.getLogger(__name__)
RUNTIME = {'__init__.py', 'client.py', 'climate.py', 'config_flow.py', 'entity.py', 'fan.py',
           'manifest.json', 'strings.json', 'translations/zh-Hans.json', 'brand/icon.png', 'brand/icon.svg'}
PUBLIC = {f'custom_components/konke_local/{name}' for name in RUNTIME} | {
    '.gitignore', '.gitattributes', 'README.md', 'LICENSE', 'CHANGELOG.md', 'hacs.json',
    'requirements-dev.txt', 'tests/test_client.py', 'scripts/validate_release.py',
    'scripts/build_package.py', '.github/workflows/checks.yml',
    '.github/ISSUE_TEMPLATE/bug_report.md', '.github/ISSUE_TEMPLATE/feature_request.md'}


def validate():
    """按正向名单检查公开文件，拒绝现场数据与未解析的发布占位符。"""
    manifest = json.loads((COMPONENT / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['domain'] == COMPONENT.name == 'konke_local'
    assert manifest['version'] == '0.1.0'
    assert manifest['integration_type'] == 'hub'
    assert manifest['iot_class'] == 'local_polling'
    assert manifest['config_flow'] is True
    assert manifest['requirements'] == ['paramiko==3.5.1']
    assert manifest['codeowners'] and all(re.fullmatch(r'@[A-Za-z0-9-]+', owner) for owner in manifest['codeowners'])
    assert manifest['issue_tracker'] == manifest['documentation'] + '/issues'
    assert json.loads((ROOT / 'hacs.json').read_text(encoding='utf-8'))['homeassistant'] == '2026.9.0'
    assert len(list((ROOT / 'custom_components').iterdir())) == 1
    strings = json.loads((COMPONENT / 'strings.json').read_text(encoding='utf-8'))
    assert strings == json.loads((COMPONENT / 'translations/zh-Hans.json').read_text(encoding='utf-8'))
    assert set(strings['config']['step']['user']['data']) == {'host', 'port', 'username', 'password', 'host_key'}
    assert {'already_configured', 'cannot_connect'} <= strings['config']['abort'].keys()
    assert "vol.Required('host'):" in (COMPONENT / 'config_flow.py').read_text(encoding='utf-8')
    for name in PUBLIC:
        assert (ROOT / name).is_file(), f'Missing release file: {name}'
    patterns = [r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
                r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}',
                r'\b192\.168\.\d{1,3}\.\d{1,3}\b', r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
                r'\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b',
                r'(?:ssh-rsa|ssh-ed25519)\s+[A-Za-z0-9+/]{100,}={0,3}']
    for path in ROOT.rglob('*'):
        relative = path.relative_to(ROOT)
        # Git 元数据、测试缓存及构建输出不属于待发布源码。
        if not path.is_file() or any(part in {'.git', '__pycache__', '.venv', 'dist'} for part in relative.parts):
            continue
        name = relative.as_posix()
        assert name in PUBLIC, f'Unexpected release file: {name}'
        if path.suffix == '.png':
            assert path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            continue
        text = path.read_text(encoding='utf-8')
        assert ('REPOSITORY' + '_OWNER') not in text, f'Unresolved owner: {name}'
        for pattern in patterns:
            assert not re.search(pattern, text), f'Sensitive material found in: {name}'
        if path.suffix == '.py':
            tree = ast.parse(text, filename=name)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    assert ast.get_docstring(node), f'Missing method documentation: {name}:{node.lineno}'
    print(f'Release validation passed: {len(PUBLIC)} allowlisted files')


if __name__ == '__main__':
    try:
        validate()
    except Exception:
        LOGGER.exception('Release validation failed')
        raise
