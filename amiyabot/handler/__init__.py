import os
import zipimport
import importlib

from itertools import chain
from collections import ChainMap

from amiyabot import log
from amiyabot.util import temp_sys_path
from amiyabot.help import Helper

from .messageHandlerDefine import *


class BotHandlerFactory:
    def __init__(self,
                 appid: str = None,
                 token: str = None,
                 adapter: Type[BotAdapterProtocol] = None):

        self.appid = appid
        self.instance: Optional[BotAdapterProtocol] = None
        if adapter:
            self.instance = adapter(appid, token)

        self._prefix_keywords: PrefixKeywords = list()

        self._event_handlers: EventHandlers = dict()
        self._message_handlers: MessageHandlers = list()
        self._exception_handlers: ExceptionHandlers = dict()
        self._after_reply_handlers: AfterReplyHandlers = list()
        self._before_reply_handlers: BeforeReplyHandlers = list()
        self._message_handler_middleware: MessageHandlerMiddleware = list()

        self._group_config: Dict[str, GroupConfig] = dict()

        self.plugins: Dict[str, Union[BotHandlerFactory, PluginInstance]] = dict()

    @property
    def prefix_keywords(self) -> PrefixKeywords:
        return self.__get_with_plugins('_prefix_keywords')

    @property
    def event_handlers(self) -> EventHandlers:
        return self.__get_with_plugins('_event_handlers')

    @property
    def message_handlers(self) -> MessageHandlers:
        return self.__get_with_plugins('_message_handlers')

    @property
    def exception_handlers(self) -> ExceptionHandlers:
        return self.__get_with_plugins('_exception_handlers')

    @property
    def after_reply_handlers(self) -> AfterReplyHandlers:
        return self.__get_with_plugins('_after_reply_handlers')

    @property
    def before_reply_handlers(self) -> BeforeReplyHandlers:
        return self.__get_with_plugins('_before_reply_handlers')

    @property
    def message_handler_middleware(self) -> MessageHandlerMiddleware:
        return self.__get_with_plugins('_message_handler_middleware')

    @property
    def group_config(self) -> Dict[str, GroupConfig]:
        return self.__get_with_plugins('_group_config')

    def __get_with_plugins(self, attr: str):
        self_attr = getattr(self, attr)
        plugin_attr = (getattr(n, attr.strip('_')) for _, n in self.plugins.items())

        attr_type = type(self_attr)

        if attr_type is list:
            return self_attr + list(chain(*plugin_attr))
        elif attr_type is dict:
            value = {**self_attr}
            plugin_value = dict(ChainMap(*plugin_attr))
            for k in plugin_value:
                if k not in value:
                    value[k] = plugin_value[k]
                else:
                    value[k] += plugin_value[k]
            return value

    def __get_prefix_keywords(self):
        return list(set(self.prefix_keywords))

    @Helper.record
    def on_message(self,
                   group_id: Union[GroupConfig, str] = None,
                   keywords: KeywordsType = None,
                   verify: VerifyMethodType = None,
                   check_prefix: CheckPrefixType = None,
                   allow_direct: Optional[bool] = None,
                   direct_only: bool = False,
                   level: int = 0):
        """
        注册消息处理器

        :param group_id:      组别 ID
        :param keywords:      触发关键字
        :param verify:        自定义校验方法
        :param check_prefix:  是否校验前缀或指定需要校验的前缀
        :param allow_direct:  是否支持用于私信
        :param direct_only:   是否仅支持私信
        :param level:         关键字校验成功后函数的候选默认等级
        :return:              注册函数的装饰器
        """

        def register(func: FunctionType):
            handler = MessageHandlerItem(func,
                                         group_id=str(group_id),
                                         group_config=self.group_config.get(str(group_id)),
                                         level=level,
                                         direct_only=direct_only,
                                         allow_direct=allow_direct,
                                         check_prefix=check_prefix,
                                         prefix_keywords=self.__get_prefix_keywords)
            if verify:
                handler.custom_verify = verify
            else:
                handler.keywords = keywords

            self._message_handlers.append(handler)

        return register

    @Helper.record
    def on_event(self, events: Union[str, List[str]]):
        """
        事件响应注册器

        :param events: 事件名或事件名列表
        :return:
        """

        def register(func: EventHandlerType):
            nonlocal events
            if type(events) is not list:
                events = [events]

            for item in events:
                if item not in self._event_handlers:
                    self._event_handlers[item] = []

                self._event_handlers[item].append(func)

        return register

    @Helper.record
    def on_exception(self, exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception):
        """
        注册异常处理器，参数为异常类型或异常类型列表，在执行通过本实例注册的所有方法产生异常时会被调用

        :param exceptions: 异常类型或异常类型列表
        :return:           注册函数的装饰器
        """

        def handler(func: ExceptionHandlerType):
            nonlocal exceptions
            if type(exceptions) is not list:
                exceptions = [exceptions]

            for item in exceptions:
                if item not in self._exception_handlers:
                    self._exception_handlers[item] = []

                self._exception_handlers[item].append(func)

        return handler

    @Helper.record
    def before_bot_reply(self, handler: BeforeReplyHandlerType):
        """
        Bot 回复前处理，用于定义当 Bot 即将回复消息时的操作，该操作会在处理消息前执行

        :param handler: 处理函数
        :return:
        """
        self._before_reply_handlers.append(handler)

    @Helper.record
    def after_bot_reply(self, handler: AfterReplyHandlerType):
        """
        Bot 回复后处理，用于定义当 Bot 回复消息后的操作，该操作会在发送消息后执行

        :param handler: 处理函数
        :return:
        """
        self._after_reply_handlers.append(handler)

    @Helper.record
    def handler_middleware(self, handler: MessageHandlerMiddlewareType):
        """
        Message 对象与消息处理器的中间件，用于对 Message 作进一步的客制化处理，允许存在多个，但会根据加载顺序叠加使用

        :param handler: 处理函数
        :return:
        """
        self._message_handler_middleware.append(handler)

    def set_group_config(self, config: GroupConfig):
        self._group_config[config.group_id] = config

    def set_prefix_keywords(self, keyword: Union[str, List[str]]):
        self._prefix_keywords += [keyword] if type(keyword) != list else keyword


class PluginInstance(BotHandlerFactory):
    def __init__(self,
                 name: str,
                 version: str,
                 plugin_id: str,
                 plugin_type: str = None,
                 description: str = None,
                 document: str = None):
        super().__init__()

        self.name = name
        self.version = version
        self.plugin_id = plugin_id
        self.plugin_type = plugin_type
        self.description = description
        self.document = document

    def install(self): ...

    def uninstall(self): ...


class BotInstance(BotHandlerFactory):
    def __init__(self,
                 appid: str = None,
                 token: str = None,
                 adapter: Type[BotAdapterProtocol] = None):
        super().__init__(
            appid,
            token,
            adapter
        )

    def install_plugin(self, plugin: Union[str, PluginInstance]):
        with log.sync_catch('plugin install error:'):
            if type(plugin) is str:
                if os.path.isdir(plugin):
                    # 以 Python Package 的形式加载
                    path_split = plugin.replace('\\', '/').split('/')
                    with temp_sys_path(os.path.abspath('/'.join(path_split[:-1]))):
                        module = importlib.import_module(path_split[-1])
                elif plugin.endswith('.py'):
                    # 以 py 文件的形式加载
                    with temp_sys_path(os.path.abspath(os.path.dirname(plugin))):
                        module = importlib.import_module(os.path.basename(plugin).strip('.py'))
                else:
                    # 以包的形式加载，方式同 Python Package
                    with temp_sys_path(os.path.abspath(plugin)):
                        module = zipimport.zipimporter(plugin).load_module('__init__')

                instance: PluginInstance = getattr(module, 'bot')
            else:
                instance = plugin

            plugin_id = instance.plugin_id

            assert plugin_id not in self.plugins, f'plugin id {plugin_id} already exists.'

            # 安装插件
            instance.set_prefix_keywords(self.prefix_keywords)
            instance.install()

            self.plugins[plugin_id] = instance

            return instance

    def uninstall_plugin(self, plugin_id: str):
        assert plugin_id != '__factory__' and plugin_id in self.plugins

        self.plugins[plugin_id].uninstall()
        del self.plugins[plugin_id]

    def combine_factory(self, factory: BotHandlerFactory):
        self.plugins['__factory__'] = factory
