import abc
import time

from typing import Any, List, Union, Optional, Callable
from dataclasses import dataclass
from amiyabot.typeIndexes import *


class EventStructure:
    def __init__(self, instance: T_BotAdapterProtocol, event_name: str, data: dict):
        self.instance = instance
        self.event_name = event_name
        self.data = data

    def __str__(self):
        return f'Bot:{self.instance.appid} Event:{self.event_name}'


class MessageStructure:
    def __init__(self, instance: T_BotAdapterProtocol, message: Optional[dict] = None):
        self.bot: Optional[T_BotHandlerFactory] = None
        self.instance = instance

        self.factory_name = ''

        self.message = message
        self.message_id = ''
        self.message_type = ''

        self.face: List[int] = []
        self.image: List[str] = []

        self.files: List[File] = []
        self.voice = ''
        self.audio = ''
        self.video = ''

        self.text = ''
        self.text_digits = ''
        self.text_unsigned = ''
        self.text_original = ''
        self.text_words: List[str] = []

        self.at_target: List[str] = []

        self.is_at = False
        self.is_at_all = False
        self.is_admin = False
        self.is_direct = False

        self.user_id = ''
        self.user_openid = ''

        self.channel_id = ''
        self.channel_openid = ''

        self.guild_id = ''
        self.src_guild_id = ''

        self.nickname = ''
        self.avatar = ''

        self.verify: Optional[Verify] = None
        self.time = int(time.time())

    def __str__(self):
        text = self.text.replace('\n', ' ')
        face = ''.join([f'[face:{n}]' for n in self.face])
        image = '[image]' * len(self.image)

        return 'Bot:{bot} Channel:{channel} User:{user}{admin}{direct} {nickname}: {message}'.format(
            **{
                'bot': self.instance.appid,
                'channel': self.channel_id,
                'user': self.user_id,
                'admin': '(admin)' if self.is_admin else '',
                'direct': '(direct)' if self.is_direct else '',
                'nickname': self.nickname,
                'message': text + face + image,
            }
        )

    @abc.abstractmethod
    async def send(self, reply: T_Chain):
        raise NotImplementedError

    @abc.abstractmethod
    async def recall(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def wait(
        self,
        reply: Optional[T_Chain] = None,
        force: bool = False,
        max_time: int = 30,
        data_filter: Optional[Callable] = None,
        level: int = 0,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def wait_channel(
        self,
        reply: Optional[T_Chain] = None,
        force: bool = False,
        clean: bool = True,
        max_time: int = 30,
        data_filter: Optional[Callable] = None,
        level: int = 0,
    ):
        raise NotImplementedError


class Verify:
    def __init__(self, result: bool, weight: Union[int, float] = 0, keypoint: Optional[Any] = None):
        self.result = result
        self.weight = weight
        self.keypoint = keypoint

    def __bool__(self):
        return bool(self.result)

    def __repr__(self):
        return f'<Verify, {self.result}, {self.weight}>'


@dataclass
class File:
    url: str
    filename: str = ''
