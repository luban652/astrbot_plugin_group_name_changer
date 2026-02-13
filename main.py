from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from typing import List, Union

@register("astrbot_plugin_group_name_changer", "Your Name", 
          "在群聊中检测到单独的五个数字消息时自动更改群名，支持aiocqhttp平台，提供群聊黑白名单管理功能", 
          "1.0.0", "")
class GroupNameChangerPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        logger.info("群名修改插件初始化完成")
        
    async def terminate(self):
        '''插件卸载时调用'''
        logger.info("群名修改插件已卸载")

    def _check_group_permission(self, group_id: str) -> bool:
        """
        检查群是否符合触发条件
        :param group_id: 群号
        :return: 是否允许触发
        """
        # 检查插件是否启用
        if not self.config.get("enable_plugin", True):
            return False
            
        white_list = self.config.get("white_list", [])
        black_list = self.config.get("black_list", [])
        
        # 白名单优先于黑名单
        if white_list:
            return group_id in white_list
        return group_id not in black_list

    def _is_valid_number(self, message: str) -> bool:
        """
        检查消息是否为有效的数字
        :param message: 消息内容
        :return: 是否为有效数字
        """
        digit_length = self.config.get("digit_length", 5)
        strict_mode = self.config.get("strict_mode", True)
        
        if strict_mode:
            return message.isdigit() and len(message) == digit_length
        return message.strip().isdigit() and len(message.strip()) == digit_length

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        """
        处理群消息事件，检测是否符合改名条件
        """
        try:
            # 检查插件是否启用
            if not self.config.get("enable_plugin", True):
                return
                
            group_id = event.get_group_id()
            message_str = event.message_str
            
            # 检查群权限
            if not self._check_group_permission(group_id):
                return
                
            # 检查管理员权限
            if self.config.get("admin_only", False) and not event.is_admin():
                return
                
            # 检查是否为有效数字
            if not self._is_valid_number(message_str):
                return
                
            # 记录日志
            if self.config.get("log_changes", True):
                logger.info(f"准备将群 {group_id} 改名为: {message_str}")
                
            # 调用QQ协议端API修改群名
            if event.get_platform_name() == "aiocqhttp":
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                assert isinstance(event, AiocqhttpMessageEvent)
                client = event.bot
                payloads = {
                    "group_id": group_id,
                    "group_name": message_str
                }
                await client.api.call_action('set_group_name', **payloads)
                
        except Exception as e:
            logger.error(f"处理群消息时出错: {str(e)}")

    @filter.command("添加白名单")
    async def add_to_white_list(self, event: AstrMessageEvent):
        """添加群到白名单"""
        await self._manage_list(event, "white_list", "添加")

    @filter.command("移除白名单")
    async def remove_from_white_list(self, event: AstrMessageEvent):
        """从白名单中移除群"""
        await self._manage_list(event, "white_list", "移除")

    @filter.command("添加黑名单")
    async def add_to_black_list(self, event: AstrMessageEvent):
        """添加群到黑名单"""
        await self._manage_list(event, "black_list", "添加")

    @filter.command("移除黑名单")
    async def remove_from_black_list(self, event: AstrMessageEvent):
        """从黑名单中移除群"""
        await self._manage_list(event, "black_list", "移除")

    async def _manage_list(self, event: AstrMessageEvent, list_name: str, operation: str):
        """
        管理黑白名单的通用方法
        :param event: 消息事件
        :param list_name: 名单名称 (white_list 或 black_list)
        :param operation: 操作类型 (添加 或 移除)
        """
        try:
            group_id = event.get_group_id()
            if not group_id:
                yield event.plain_result("请在群聊中使用此命令")
                return
                
            current_list = self.config.get(list_name, [])
            
            if operation == "添加":
                if group_id in current_list:
                    yield event.plain_result(f"该群已在{list_name}中")
                else:
                    current_list.append(group_id)
                    yield event.plain_result(f"已成功将群添加到{list_name}")
            else:
                if group_id in current_list:
                    current_list.remove(group_id)
                    yield event.plain_result(f"已成功从{list_name}中移除群")
                else:
                    yield event.plain_result(f"该群不在{list_name}中")
                    
            # 更新配置
            self.config[list_name] = current_list
            self.config.save_config()
            
        except Exception as e:
            logger.error(f"管理{list_name}时出错: {str(e)}")
            yield event.plain_result(f"操作失败: {str(e)}")

    @filter.command("查看名单")
    async def view_lists(self, event: AstrMessageEvent):
        """查看当前的黑白名单状态"""
        try:
            white_list = self.config.get("white_list", [])
            black_list = self.config.get("black_list", [])
            
            message = "当前名单状态:\n"
            message += f"白名单({len(white_list)}个): {', '.join(white_list) if white_list else '空'}\n"
            message += f"黑名单({len(black_list)}个): {', '.join(black_list) if black_list else '空'}\n"
            message += f"当前模式: {'白名单优先' if white_list else '黑名单过滤'}"
            
            yield event.plain_result(message)
        except Exception as e:
            logger.error(f"查看名单时出错: {str(e)}")
            yield event.plain_result(f"获取名单失败: {str(e)}")