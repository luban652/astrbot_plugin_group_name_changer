from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from typing import Dict, List
import time
import json

@register("astrbot_plugin_group_name_changer", "Anonymous", 
          "自动检测群聊中的五个数字消息并更改群名为该数字，支持aiocqhttp平台，提供黑白名单管理功能", 
          "1.0.0", "")
class GroupNameChangerPlugin(Star):
    def __init__(self, context: Context, config: Dict):
        super().__init__(context)
        self.config = config
        self.last_change_time: Dict[str, float] = {}  # 记录每个群最后修改时间 {group_id: timestamp}
        
        # 初始化配置
        self.enable_plugin = self.config.get("enable_plugin", True)
        self.require_admin = self.config.get("require_admin", False)
        self.whitelist = self.config.get("whitelist", [])
        self.blacklist = self.config.get("blacklist", [])
        self.number_length = self.config.get("number_length", 5)
        self.cooldown_time = self.config.get("cooldown_time", 60)
        self.log_changes = self.config.get("log_changes", True)
        
        logger.info("群名修改插件已加载")

    async def terminate(self):
        '''插件卸载时调用'''
        logger.info("群名修改插件已卸载")

    @filter.command("添加白名单")
    async def add_to_whitelist(self, event: AstrMessageEvent):
        '''将当前群聊添加到白名单'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令")
            return
            
        if group_id in self.whitelist:
            yield event.plain_result("当前群聊已在白名单中")
            return
            
        self.whitelist.append(group_id)
        self.config["whitelist"] = self.whitelist
        self.config.save_config()
        yield event.plain_result("已添加当前群聊到白名单")

    @filter.command("移除白名单")
    async def remove_from_whitelist(self, event: AstrMessageEvent):
        '''将当前群聊从白名单移除'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令")
            return
            
        if group_id not in self.whitelist:
            yield event.plain_result("当前群聊不在白名单中")
            return
            
        self.whitelist.remove(group_id)
        self.config["whitelist"] = self.whitelist
        self.config.save_config()
        yield event.plain_result("已从白名单移除当前群聊")

    @filter.command("添加黑名单")
    async def add_to_blacklist(self, event: AstrMessageEvent):
        '''将当前群聊添加到黑名单'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令")
            return
            
        if group_id in self.blacklist:
            yield event.plain_result("当前群聊已在黑名单中")
            return
            
        self.blacklist.append(group_id)
        self.config["blacklist"] = self.blacklist
        self.config.save_config()
        yield event.plain_result("已添加当前群聊到黑名单")

    @filter.command("移除黑名单")
    async def remove_from_blacklist(self, event: AstrMessageEvent):
        '''将当前群聊从黑名单移除'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此指令")
            return
            
        if group_id not in self.blacklist:
            yield event.plain_result("当前群聊不在黑名单中")
            return
            
        self.blacklist.remove(group_id)
        self.config["blacklist"] = self.blacklist
        self.config.save_config()
        yield event.plain_result("已从黑名单移除当前群聊")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_group_message(self, event: AstrMessageEvent):
        '''监听群消息，检测符合条件的数字并修改群名'''
        try:
            # 检查插件是否启用
            if not self.enable_plugin:
                return
                
            group_id = event.get_group_id()
            message_str = event.message_str.strip()
            
            # 检查群聊是否在黑名单中
            if group_id in self.blacklist:
                return
                
            # 检查群聊是否在白名单中（如果白名单不为空）
            if self.whitelist and group_id not in self.whitelist:
                return
                
            # 检查是否需要管理员权限
            if self.require_admin and not event.get_sender_is_admin():
                return
                
            # 检查消息是否为纯数字且长度符合要求
            if not message_str.isdigit() or len(message_str) != self.number_length:
                return
                
            # 检查冷却时间
            current_time = time.time()
            last_time = self.last_change_time.get(group_id, 0)
            if current_time - last_time < self.cooldown_time:
                if self.log_changes:
                    logger.info(f"群 {group_id} 修改群名冷却中，跳过修改")
                return
                
            # 记录修改时间
            self.last_change_time[group_id] = current_time
            
            # 调用QQ协议端API修改群名
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                
                payloads = {
                    "group_id": int(group_id),
                    "group_name": message_str
                }
                
                try:
                    ret = await client.api.call_action('set_group_name', **payloads)
                    if self.log_changes:
                        logger.info(f"成功修改群 {group_id} 名称为 {message_str}, 返回: {ret}")
                except Exception as e:
                    logger.error(f"修改群名失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"处理群消息时出错: {str(e)}")
