import json
import asyncio
import websockets

from typing import Callable
from amiyabot.adapters import BotAdapterProtocol
from amiyabot.builtin.messageChain import Chain
from amiyabot.log import LoggerManager

from .package import package_mirai_message
from .builder import build_message_send

log = LoggerManager('Mirai')


def mirai_api_http(host: str, ws_port: int, http_port: int):
    def adapter(appid: str, token: str):
        return MiraiBotInstance(appid, token, host, ws_port, http_port)

    return adapter


class MiraiBotInstance(BotAdapterProtocol):
    def __init__(self, appid: str, token: str, host: str, ws_port: int, http_port: int):
        super().__init__(appid, token)

        self.url = f'ws://{host}:{ws_port}/all?verifyKey={token}&&qq={appid}'

        self.connection: websockets.WebSocketClientProtocol = None

        self.host = host
        self.ws_port = ws_port
        self.http_port = http_port

        self.session = None
        self.alive = True

    def __str__(self):
        return 'Mirai'

    async def connect(self, private: bool, handler: Callable):
        mark = f'websocket({self.appid})'

        log.info(f'connecting {mark}...')
        try:
            async with websockets.connect(self.url) as websocket:
                log.info(f'{mark} connect successful. waiting handshake...')
                self.connection = websocket
                while self.alive:
                    message = await websocket.recv()

                    if message == b'':
                        await websocket.close()
                        return False

                    await self.handle_message(str(message), handler)

                await websocket.close()

                log.info(f'{mark} closed.')

        except websockets.ConnectionClosedOK as e:
            log.error(f'{mark} connection closed. {e}')
        except ConnectionRefusedError:
            log.error(f'cannot connect to mirai-api-http {mark} server.')

        await asyncio.sleep(10)
        asyncio.create_task(self.connect(private, handler))

    async def handle_message(self, message: str, handler: Callable):
        async with log.catch(ignore=[json.JSONDecodeError]):
            data = json.loads(message)
            data = data['data']

            if 'session' in data:
                self.session = data['session']
                log.info('websocket handshake successful. session: ' + self.session)
                return False

            asyncio.create_task(handler('', data))

    async def send_chain_message(self, chain: Chain):
        reply, voice_list = await build_message_send(f'{self.host}:{self.http_port}', self.session, chain)

        if reply:
            await self.connection.send(reply)

        if voice_list:
            chain.reference = False
            for voice in voice_list:
                await self.connection.send(voice)

    async def send_message(self, channel_id: str = '', user_id: str = '', direct_src_guild_id: str = ''):
        pass

    async def package_message(self, event: str, message: dict):
        return package_mirai_message(self, self.appid, message)
