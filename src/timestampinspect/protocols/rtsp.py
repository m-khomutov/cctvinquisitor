"""Rtsp client"""
import selectors
import socket
from base64 import b64encode
from collections import namedtuple
from enum import IntEnum
from typing import Tuple, Union
from .interface import Interface
from ..display.display import DisplayForm, DisplayException


State: IntEnum = IntEnum('State', ('INITIAL',
                                   'DESCRIBED',
                                   'SETUP',
                                   'ASK_PLAYING',
                                   'PLAYING')
                         )


class UnitType(IntEnum):
    NonIDR = 1,
    IDR = 5,
    FU_A = 28


RtpInterleaved: namedtuple = namedtuple('RtpInterleaved', 'preamble channel size')
RtpHeader: namedtuple = namedtuple('RtpHeader', 'version P X CC M pt cseq timestamp ssrc')
UnitHeader: namedtuple = namedtuple('UnitHeader', 'f nri type')
FUHeader: namedtuple = namedtuple('FUHeader', 's e r type')


class Source(Interface):
    def __init__(self, form: DisplayForm, credentials: list, content: str) -> None:
        self.form: DisplayForm = form
        self.credentials = credentials
        self.content: str = content
        self._sequence: int = 1
        self._buffer: bytearray = bytearray()
        self._interleaved: RtpInterleaved = RtpInterleaved('$', 0, 0)
        self._state: State = State.INITIAL
        self.url: str = ''
        self._control: list = []
        self._session: str = ''
        self._transport: str = ''
        self.range = []
        self._authorization: str = ''
        self.timestamp_delta: list = [0, 0]

    def stream_request(self, address: str, port: int) -> bytes:
        self.url = f'rtsp://{address}:{port}/{self.content}' + self.url
        return f"OPTIONS {self.url} RTSP/1.0\r\n" \
               f"CSeq: {self._sequence}\r\n" \
               f"User-Agent: pyCCTV_front\r\n" \
               f"{self._authorization}\r\n".encode()

    def on_action_reply(self, data: bytes) -> None:
        pass

    def on_stream(self, key: selectors.SelectorKey, data: bytes, expected_length: int) -> int:
        if self._state == State.PLAYING:
            self._on_rtp_data(data)
        else:
            try:
                if self._session:
                    reply_end = data.find(0x24)
                else:
                    reply_end = data.find(b'\x0d\x0a\x0d\x0a')
                if reply_end != 0:
                    key.data.outb = self._on_rtsp_dialog(data[:reply_end].decode('utf-8').split('\r\n'),
                                                         data[reply_end + 4:])
                elif reply_end >= 0 and self._session:
                    self._state = State.PLAYING
                    self._on_rtp_data(data[reply_end:])
            except UnicodeDecodeError:
                self._state = State.PLAYING
        return len(data)

    def add_action(self,
                   selector: selectors.DefaultSelector,
                   stream_socket: socket.socket,
                   address: str,
                   port: int,
                   action: Tuple[str, str]) -> Union[socket.socket, None]:
        return None

    def clear(self):
        self._state: State = State.INITIAL
        self._session = ''
        self.timestamp_delta = [0, 0]
        self._buffer.clear()

    def _on_rtsp_dialog(self, headers: list, remains: bytes) -> bytes:
        self.form.log_rtsp('\n'.join(headers)+'\n')
        self._set_status(headers[0])
        rc = b''
        if not (self._status == 200 or self._status == 401):
            raise DisplayException(f'Source {self.url} not found')
        for hdr in headers:
            out_bytes: bytes = {
                'CSeq': self._set_sequence,
                'Public': self._ask_describe,
                'Content-Base': self._set_content_base,
                'Session': self._set_session,
                'Transport': self._set_transport,
                'WWW-Authenticate': self._set_authentication
            }.get(hdr.split(':')[0], lambda **h: b'')(header=hdr, body=remains)
            if out_bytes:
                self.form.log_rtsp(out_bytes.decode('utf-8'))
                rc = out_bytes
        if self._state == State.SETUP:
            rc = self._ask_play()
            self.form.log_rtsp(rc.decode('utf-8'))
        return rc

    def _on_rtp_data(self, data: bytes):
        self._buffer += data
        while True:
            interleaved: RtpInterleaved = RtpInterleaved(str(self._buffer[0]),
                                                         self._buffer[1],
                                                         int.from_bytes(self._buffer[2:4], byteorder='big'))
            if len(self._buffer) > interleaved.size + 8:
                header: RtpHeader = RtpHeader((self._buffer[4] >> 6) & 3,
                                              (self._buffer[4] >> 5) & 1,
                                              (self._buffer[4] >> 4) & 1,
                                              (self._buffer[4]) & 0xf,
                                              (self._buffer[5] >> 7) & 1,
                                              (self._buffer[5]) & 0x7f,
                                              int.from_bytes(self._buffer[6:8], byteorder='big'),
                                              int.from_bytes(self._buffer[8:12], byteorder='big'),
                                              int.from_bytes(self._buffer[12:16], byteorder='big'))
                unit: UnitHeader = UnitHeader(self._buffer[16] >> 7,
                                              (self._buffer[16] >> 5) & 3,
                                              (self._buffer[16]) & 0x1f)
                if unit.type == UnitType.FU_A:
                    fu_header: FUHeader = FUHeader(self._buffer[17] >> 7,
                                                   (self._buffer[17] >> 6) & 1,
                                                   (self._buffer[17] >> 5) & 1,
                                                   (self._buffer[17]) & 0x1f)
                    if fu_header.e:
                        self._initialize_timestamp_set(header)
                        self.form.log_rtp(f'Rtp(type={fu_header.type},'
                                          f' ts={header.timestamp},'
                                          f' delta={header.timestamp - self.timestamp_delta[1]})')
                        self.timestamp_delta[1] = header.timestamp
                else:
                    self._initialize_timestamp_set(header)
                    self.form.log_rtp(f'Rtp(type={unit.type},'
                                      f' ts={header.timestamp},'
                                      f' delta={header.timestamp - self.timestamp_delta[1]})')
                    self.timestamp_delta[1] = header.timestamp
                self._buffer = self._buffer[interleaved.size + 4:]
            else:
                break

    def _initialize_timestamp_set(self, header: RtpHeader):
        if not self.timestamp_delta[0]:
            self.timestamp_delta = [header.timestamp, header.timestamp]

    def _set_status(self, header: str) -> None:
        self._status = int(header.split()[1])

    def _set_sequence(self, **kwargs) -> None:
        self._sequence = int(kwargs.get('header').split()[1]) + 1

    def _set_content_base(self, **kwargs) -> bytes:
        body: bytes = kwargs.get('body')
        self.form.log_rtsp(body.decode("utf-8"))
        self._state = State.DESCRIBED
        self._content_base = kwargs.get('header').split()[1]
        description = body.decode('utf-8').split('\r\n')
        self._control = [x.split(':')[1] for x in description if 'a=control:' in x and '*' not in x]
        if not self.range:
            self.range = [x.split(':')[1].split('=')[1] for x in description if 'a=range:' in x][0].split('-')
        return f'SETUP {self._content_base}{self._control[0]} RTSP/1.0\r\n'\
               f'Transport: RTP/AVP/TCP;unicast;interleaved=0-1\r\n' \
               f'CSeq: {self._sequence}\r\n' \
               f'User-Agent: pyCCTV_front\r\n' \
               f'{self._authorization}\r\n'.encode()

    def _set_session(self, **kwargs) -> None:
        if not self._session:
            self._state = State.SETUP
            self._session = kwargs.get('header').split()[1]
        else:
            self._state = State.PLAYING

    def _set_transport(self, **kwargs) -> None:
        self._transport = kwargs.get('header').split()[1]

    def _set_authentication(self, **kwargs) -> bytes:
        realm = kwargs.get('header').split()[1]
        if realm.startswith('Basic'):
            self._authorization = 'Authorization: Basic ' + \
                                  b64encode(f'{self.credentials[0]}:'
                                            f'{self.credentials[1]}'.encode()).decode('ascii') +\
                                    '\r\n'
        return self._ask_describe()

    def _ask_describe(self, **kwargs) -> bytes:
        return f'DESCRIBE {self.url} RTSP/1.0\r\n' \
               f'Accept: application/sdp\r\n' \
               f'CSeq: {self._sequence}\r\n' \
               f'User-Agent: pyCCTV_front\r\n' \
               f'{self._authorization}\r\n'.encode()

    def _ask_play(self) -> bytes:
        self._state = State.ASK_PLAYING
        range_type: str = 'clock' if 'T' in self.range[0] else 'npt'
        return f'PLAY {self._content_base} RTSP/1.0\r\n' \
               f'CSeq: {self._sequence}\r\n' \
               f'Range: {range_type}={self.range[0]}-{self.range[1]}\r\n' \
               f'User-Agent: pyCCTV_front\r\n' \
               f'Session: {self._session}\r\n' \
               f'{self._authorization}\r\n'.encode()
