"""Displays flv stream data and http protocol commands"""
from .display import DisplayForm, MultilineBox
from typing import Tuple


class CctvForm(DisplayForm):
    """Form to display data"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._size: Tuple[int, int] = (0, 0)

    def create(self) -> None:
        self._size = self.useable_space()
        horizontal_div: int = (self._size[1] * 2) // 3
        vertical_div: int = self._size[0] // 4
        self.keypress_timeout = 1
        super().set_menu('actions')
        self._http_box = self.add(MultilineBox,
                                  name='http',
                                  editable=False,
                                  scroll_exit=True,
                                  relx=2,
                                  max_width=horizontal_div,
                                  rely=vertical_div,
                                  max_height=(self._size[0] - vertical_div - 2))
        self._flv_box = self.add(MultilineBox,
                                 name='flv',
                                 editable=False,
                                 scroll_exit=True,
                                 relx=horizontal_div + 2,
                                 max_width=(self._size[1] - horizontal_div - 4),
                                 rely=2,
                                 max_height=self._size[0] - 4)
        self._position_box = self.add(MultilineBox,
                                      name='position',
                                      editable=False,
                                      scroll_exit=True,
                                      relx=2,
                                      max_width=horizontal_div,
                                      rely=2,
                                      max_height=(vertical_div - 2))
        self.parentApp.on_created(self)

    def log_http(self, value: str) -> None:
        DisplayForm._to_box(self._http_box, value)

    def log_rtsp(self, value: str) -> None:
        pass

    def log_rtp(self, value: str) -> None:
        pass

    def log_flv(self, value: str) -> None:
        DisplayForm._to_box(self._flv_box, value)

    def log_position(self, value: str) -> None:
        DisplayForm._to_box(self._position_box, value)

    def log_error(self, value: str) -> None:
        DisplayForm._to_box(self._http_box, value)

    def _on_waiting(self) -> None:
        self._flv_box.display()
        self._http_box.display()
        self._position_box.display()
