"""CCTV-DVR client. Uses flv container for streaming and http for commands"""
import json
import selectors
import socket
from collections import namedtuple
from typing import List, Tuple, Dict, Union
import types
from .interface import Interface
from ..display.display import DisplayForm


FlvHeader: namedtuple = namedtuple('FlvHeader', 'signature version audio video offset')
FlvTag: namedtuple = namedtuple('FlvTag', 'type, size, timestamp, sid')


class FlvParser:
    """Class to parse flv header, previous tag size and flv tag"""
    def __init__(self):
        self._header: FlvHeader = FlvHeader('', 0, False, False, 0)
        self._previous_tag_size: int = 0
        self._tag: FlvTag = FlvTag(0, 0, 0, 0)

    @property
    def tag(self):
        return self._tag

    def ready(self) -> bool:
        return True if self._header.signature else False

    def parse(self, data: bytes):
        offset: int = 0
        if not self._header.signature:
            self._header = FlvHeader(data[:3].decode('utf-8'),
                                     int(data[3]),
                                     (data[4] >> 2) & 1,
                                     (data[4]) & 1,
                                     int.from_bytes(data[5:9], byteorder='big'))
            offset = self._header.offset
        self._previous_tag_size = int.from_bytes(data[offset:offset+13], byteorder='big')
        offset += 4
        self._tag = FlvTag(int(data[offset]),
                           int.from_bytes(data[offset+1:offset+4], byteorder='big'),
                           int.from_bytes(bytearray(data[offset+7])+data[offset+4:offset+7], byteorder='big'),
                           int.from_bytes(data[offset+8:offset+11], byteorder='big'))
        return offset + 11 + self._tag.size

    def __repr__(self):
        return str(self._header)


class Source(Interface):
    def __init__(self, form: DisplayForm, content: str, control_port: int) -> None:
        self._form: DisplayForm = form
        self._content: str = content
        self._control_port: int = control_port
        self._buffer: bytearray = bytearray()
        self._parser: FlvParser = FlvParser()
        elements: List[str, ...] = content.split('/')
        self._control: str = ''
        if len(elements) > 2 and elements[-1] == elements[-2] == '0':
            self._control = elements[-3]
        self._timestamp_delta: List[int, int] = [0, 0]

    def stream_request(self, address: str, port: int) -> bytes:
        return f'GET /{self._content} HTTP/1.0\r\n' \
               f'User-Agent: pyCCTV_front\r\n'\
               f'Accept: */*\r\n'\
               f'Range: bytes=0-\r\n'\
               f'Connection: close\r\n'\
               f'Host: {address}:{port}\r\n'\
               f'Icy-MetaData: 1\r\n\r\n'.encode()

    def on_action_reply(self, data: bytes) -> None:
        headers: List[str, ...] = data.decode('utf-8').split('\r\n')
        js: Dict[str, str] = json.loads(headers[-1])
        if int(headers[0].split()[-2]) == 200 and 'position' in js:
            self._form.log_position(f'{js["position"]}')
        self._form.log_http(data.decode('utf-8'))

    def on_stream(self, key: selectors.SelectorKey, data: bytes, expected_length: int) -> int:
        self._buffer += data
        if not self._parser.ready():
            pos = self._buffer.find(b'\x0d\x0a\x0d\x0a')
            if pos > 0:
                http_reply: str = self._buffer[:pos + 4].decode('utf-8')
                self._form.log_http(http_reply)
                self._buffer = self._buffer[pos + 4:]
                expected_length = self._parser.parse(self._buffer)
                self._set_timestamp()
                self._form.log_flv(f'{self._parser}\n'
                                   f'ts={self._parser.tag.timestamp}, '
                                   f'delta={self._parser.tag.timestamp - self._timestamp_delta[1]}')
                self._timestamp_delta[1] = self._parser.tag.timestamp
        elif len(self._buffer) >= expected_length + 15:
            self._buffer = self._buffer[expected_length:]
            expected_length = self._parser.parse(self._buffer)
            self._set_timestamp()
            self._form.log_flv(f'ts={self._parser.tag.timestamp}, '
                               f'delta={self._parser.tag.timestamp - self._timestamp_delta[1]}')
            self._timestamp_delta[1] = self._parser.tag.timestamp
        return expected_length

    def add_action(self,
                   selector: selectors.DefaultSelector,
                   stream_socket: socket.socket,
                   address: str,
                   port: int,
                   action: Tuple[str, str]) -> Union[socket.socket, None]:
        s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((address, self._control_port))
        s.setblocking(False)
        stream_request: bytes = self._action_request(address, action)
        self._form.log_http(stream_request.decode('utf-8'))
        selector.register(s,
                          selectors.EVENT_READ | selectors.EVENT_WRITE,
                          types.SimpleNamespace(addr=self._control_port, inb=b'', outb=stream_request))
        return None

    def _action_request(self, address: str, action: Tuple[str, str]) -> bytes:
        request = f'GET /?control={self._control}&action={action[0]}'
        if len(action) == 2:
            request = request + f'&pos={action[1]}'
        return (request + f'&sec HTTP/1.0\r\nHost: {address}:{self._control_port}\r\n\r\n').encode()

    def _set_timestamp(self):
        if not self._timestamp_delta[0]:
            self._timestamp_delta[0] = self._parser.tag.timestamp
            self._timestamp_delta[1] = self._parser.tag.timestamp
