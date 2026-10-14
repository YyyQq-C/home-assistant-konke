"""验证控客组帧、状态映射及设备命令隔离。"""
import importlib.util
from pathlib import Path
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('konke_client', ROOT / 'custom_components/konke_local/client.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Channel:
    """模拟分片 TCP 接收。"""

    def __init__(self, chunks):
        """保存分片。"""
        self.chunks = iter(chunks)

    def settimeout(self, timeout):
        """记录超时参数。"""
        self.timeout = timeout

    def recv(self, length):
        """逐次返回分片。"""
        return next(self.chunks, b'')


class ClientTests(unittest.TestCase):
    """验证协议边界和单设备控制参数。"""

    def test_fragmented_and_joined_frames(self):
        """分片与多帧合并不能丢失后续响应。"""
        channel = Channel([b'!{"sta', b'tus":"success"}$!{"opcode":"QUERY"}$'])
        first, pending = module.KonkeClient._receive(channel, time.monotonic() + 1, b'')
        second, pending = module.KonkeClient._receive(channel, time.monotonic() + 1, pending)
        self.assertEqual(first, {'status': 'success'})
        self.assertEqual(second, {'opcode': 'QUERY'})
        self.assertEqual(pending, b'')

    def test_partial_ac_setting_preserves_power_and_modes(self):
        """改温度时不能默认开启空调或覆盖当前风速。"""
        client = module.KonkeClient({})
        state = {'on': False, 'runModel': 'COLD', 'fanSpeed': 'MID', 'settingTemperature': 20}
        client.snapshot = lambda: {'ac_2': {'id': '2', 'kind': 'ac', 'online': True, 'state': state}}
        calls = []
        client.request = lambda *args: calls.append(args)
        client.control('ac_2', {'settingTemperature': 22})
        self.assertEqual(calls, [('CENTRAL_AC_INDOOR_UNIT_SETTING', '2', dict(state, settingTemperature=22), 'HJ_CentralAC')])

    def test_offline_device_does_not_send_commands(self):
        """离线地暖通道不得下发指令。"""
        client = module.KonkeClient({})
        client.snapshot = lambda: {'floor_901': {'online': False}}
        with self.assertRaises(ConnectionError):
            client.control('floor_901', {'on': True})

    def test_floor_and_fresh_commands_target_only_selected_node(self):
        """单设备命令不能使用网关批量控制。"""
        for key, kind, node, changes, expected in [
            ('floor_902', 'floor', '902', {'settingTemperature': 15.5}, ('SET_FLOOR_HEATING_DEV_TEMPERATURE', '902', '15.5')),
            ('fresh_903', 'fresh', '903', {'speed': 2}, ('SET_FRESH_AIR_SPEED', '903', '2'))]:
            client = module.KonkeClient({})
            client.snapshot = lambda: {key: {'id': node, 'kind': kind, 'online': True, 'state': {}}}
            calls = []
            client.request = lambda *args: calls.append(args)
            client.control(key, changes)
            self.assertEqual(calls, [expected])

    def test_temperature_boundaries_and_rejection(self):
        """允许上下限温度，越界及非有限值不能下发设备命令。"""
        for kind, minimum, maximum in [('ac', 16, 32), ('floor', 5, 45)]:
            for value in [minimum, maximum, minimum - 0.5, maximum + 0.5, float('nan'), float('inf')]:
                with self.subTest(kind=kind, value=value):
                    client = module.KonkeClient({})
                    state = {'on': False, 'runModel': 'COLD', 'fanSpeed': 'LOW', 'settingTemperature': 20}
                    client.snapshot = lambda: {'target': {'id': '900', 'kind': kind, 'online': True, 'state': state}}
                    calls = []
                    client.request = lambda *args: calls.append(args)
                    if minimum <= value <= maximum:
                        client.control('target', {'settingTemperature': value})
                        self.assertEqual(len(calls), 1)
                    else:
                        with self.assertRaises(ValueError):
                            client.control('target', {'settingTemperature': value})
                        self.assertEqual(calls, [])

    def test_closed_connection_and_oversized_frame(self):
        """截断消息和过大消息必须终止，不返回伪造成功。"""
        for chunks, exception in [([b'!{"incomplete":'], ConnectionError), ([b'!' + b'x' * 1048576], ValueError)]:
            with self.subTest(exception=exception):
                with self.assertRaises(exception):
                    module.KonkeClient._receive(Channel(chunks), time.monotonic() + 1, b'')

    def test_pinned_host_key_and_reject_policy(self):
        """非默认端口也必须绑定指定公钥，未知公钥拒绝连接。"""
        with patch.object(module.paramiko, 'SSHClient') as ssh_class, patch.object(module.paramiko.PKey, 'from_type_string') as parse_key:
            # 合成公钥由模拟解析器接收，不是任何设备的实际公钥。
            client = module.KonkeClient({'host': 'gateway.example.invalid', 'port': 2222,
                                        'username': 'example', 'password': 'example-only', 'host_key': 'ssh-rsa ZmFrZQ=='})
            client._connect()
            ssh = ssh_class.return_value
            ssh.get_host_keys.return_value.add.assert_called_once_with('[gateway.example.invalid]:2222', 'ssh-rsa', parse_key.return_value)
            policy = ssh.set_missing_host_key_policy.call_args.args[0]
            self.assertIsInstance(policy, module.paramiko.RejectPolicy)
            with self.assertRaises(module.paramiko.SSHException):
                policy.missing_host_key(ssh, 'unknown.example.invalid', module.paramiko.RSAKey.generate(1024))
            self.assertFalse(ssh.connect.call_args.kwargs['allow_agent'])
            self.assertFalse(ssh.connect.call_args.kwargs['look_for_keys'])


if __name__ == '__main__':
    unittest.main()
