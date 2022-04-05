"""Axon client. Uses rtsp/rtp with some command deviation"""
import json
import selectors
import socket
import types
from base64 import b64encode
from datetime import datetime
from typing import Tuple, Union
from .interface import Interface
from ..display.display import DisplayForm
from .rtsp import Source as GenericRtsp


class Source(Interface):
    def __init__(self, form: DisplayForm, address: str, credentials: list, content: str) -> None:
        self._generic: GenericRtsp = GenericRtsp(form, credentials, content)
        self._speed: int = 1
        r = self._get_range(address)
        self._generic.range = [r['start'], r['end']]
        self._generic.url = f'/{self._generic.range[0]}?speed={self._speed}'

    def stream_request(self, address: str, port: int) -> bytes:
        return self._generic.stream_request(address, port)

    def on_action_reply(self, data: bytes) -> None:
        pass

    def on_stream(self, key: selectors.SelectorKey, data: bytes, expected_length: int) -> int:
        return self._generic.on_stream(key, data, expected_length)

    def add_action(self,
                   selector: selectors.DefaultSelector,
                   stream_socket: socket.socket,
                   address: str,
                   port: int,
                   action: Tuple[str, str]) -> Union[socket.socket, None]:
        if action[0] == 'scale':
            self._reset_range_start()
            self._speed = int(action[1])
        elif 'seek' in action[0]:
            self._generic.range[0] = action[1]
        else:
            return None
        self._generic.url = f'/{self._generic.range[0]}?speed={self._speed}'
        self._generic.clear()
        stream_socket.close()
        selector.unregister(stream_socket)
        return self._set_action_socket(selector, address, port)

    def _get_range(self, address: str) -> dict:
        port: int = 80
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((address, port))
        l: list = self._generic.content.split('/hosts/')
        l.insert(1, '/statistics/depth/')
        authorization: str = ''
        if self._generic.credentials:
            authorization = 'Authorization: Basic ' + \
                            b64encode(f'{self._generic.credentials[0]}:'
                                      f'{self._generic.credentials[1]}'.encode()).decode('ascii')
        s.sendall(f'GET /{"".join(l)} HTTP/1.0\r\n'
                  f'User-Agent: pyCCTV_front\r\n'
                  f'Accept: */*\r\n'
                  f'Host: {address}:{port}\r\n'
                  f'{authorization}\r\n\r\n'.encode())
        buffer: bytearray = bytearray()
        content_length = 0
        while True:
            buffer += s.recv(1024)
            self._generic.form.log_http(buffer.decode('utf-8'))
            pos: int = buffer.find(b'\x0d\x0a\x0d\x0a')
            if pos != -1:
                for hdr in buffer[:pos].decode('utf-8').split('\r\n'):
                    if 'Content-Length:' in hdr:
                        content_length = int(hdr.split()[1])
                buffer = buffer[pos+4:]
            if content_length and len(buffer) >= content_length:
                return json.loads(buffer.decode('utf-8'))

    def _reset_range_start(self):
        from_: str = self._generic.range[0] if self._generic.range[0].find('.') == -1\
            else self._generic.range[0].split('.')[0] + 'Z'
        start: int = datetime.strptime(from_, "%Y%m%dT%H%M%SZ").timestamp() +\
            (self._generic.timestamp_delta[1] - self._generic.timestamp_delta[0]) / 90000
        self._generic.range[0] = datetime.fromtimestamp(start).strftime('%Y%m%dT%H%M%S') + 'Z'

    def _set_action_socket(self, selector: selectors.DefaultSelector,
                           address: str,
                           port: int) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((address, port))
        s.setblocking(False)
        selector.register(s,
                          selectors.EVENT_READ | selectors.EVENT_WRITE,
                          types.SimpleNamespace(addr=port,
                                                inb=b'',
                                                outb=self.stream_request(address, port)))
        return s
