"""视频字段配置（界面填写，仅当次运行有效，不单独落盘）。"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PERSONAL_PRICE = 80
DEFAULT_CREATION_TIME = "2026"


@dataclass
class VideoFieldSettings:
    personal_price: int = DEFAULT_PERSONAL_PRICE
    creation_time: str = DEFAULT_CREATION_TIME

    def to_dict(self) -> dict:
        return {
            "personal_price": self.personal_price,
            "creation_time": self.creation_time,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VideoFieldSettings:
        return cls(
            personal_price=int(data.get("personal_price", DEFAULT_PERSONAL_PRICE)),
            creation_time=str(data.get("creation_time", DEFAULT_CREATION_TIME)).strip()
            or DEFAULT_CREATION_TIME,
        )


def load_field_settings() -> VideoFieldSettings:
    return VideoFieldSettings()


def save_field_settings(settings: VideoFieldSettings) -> None:
    """界面配置仅当次运行有效，不写入文件。"""
    del settings
