"""
AstrBot 插件：极趣待办 (Zectrix Todo)
与极趣实验室 AI 待办清单硬件交互，支持待办管理、页面推送等全部 API 功能。
"""

import json
import os
import tempfile

import aiohttp
from astrbot.api import star, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import register, Context

PRIORITY_MAP = {"普通": 0, "重要": 1, "紧急": 2, "0": 0, "1": 1, "2": 2}
PRIORITY_EMOJI = {0: "⬜ 普通", 1: "🟡 重要", 2: "🔴 紧急"}
REPEAT_MAP = {
    "无": "none", "不重复": "none",
    "每天": "daily", "每日": "daily",
    "每周": "weekly", "每月": "monthly", "每年": "yearly",
    "daily": "daily", "weekly": "weekly",
    "monthly": "monthly", "yearly": "yearly", "none": "none",
}
STATUS_EMOJI = {0: "⬜", 1: "✅"}


def _parse_kv(text: str) -> dict:
    result = {}
    if not text:
        return result
    for part in text.split():
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip("\"'")
    return result


def _fmt_todo(todo: dict) -> str:
    status = STATUS_EMOJI.get(todo.get("status", 0), "⬜")
    priority = PRIORITY_EMOJI.get(todo.get("priority", 0), "⬜ 普通")
    title = todo.get("title", "")
    tid = todo.get("id", "")
    due = ""
    if todo.get("dueDate"):
        due = f"📅 {todo['dueDate']}"
        if todo.get("dueTime"):
            due += f" {todo['dueTime']}"
    desc = todo.get("description", "")
    repeat = todo.get("repeatType", "none")
    repeat_str = "" if repeat in (None, "none") else f"🔁 {repeat}"

    parts = [f"{status} [{tid}] {title}  {priority}"]
    if due:
        parts.append(f"   {due}")
    if repeat_str:
        parts.append(f"   {repeat_str}")
    if desc:
        parts.append(f"   📝 {desc}")
    return "\n".join(parts)


def _build_todo_body(kv: dict, default_device: str) -> dict:
    body = {}
    for k in ("title", "dueDate", "dueTime"):
        if k in kv:
            body[k] = kv[k]
    if "desc" in kv:
        body["description"] = kv["desc"]
    if "description" in kv:
        body["description"] = kv["description"]
    if "priority" in kv:
        p = kv["priority"]
        body["priority"] = PRIORITY_MAP.get(p, int(p) if p.isdigit() else 0)
    if "repeat" in kv:
        body["repeatType"] = REPEAT_MAP.get(kv["repeat"], "none")
    if "repeatType" in kv:
        body["repeatType"] = REPEAT_MAP.get(kv["repeatType"], kv["repeatType"])
    for rk in ("repeatWeekday", "repeatMonth", "repeatDay"):
        if rk in kv:
            body[rk] = int(kv[rk])
    if "deviceId" in kv:
        body["deviceId"] = kv["deviceId"]
    elif default_device:
        body["deviceId"] = default_device
    return body


@register(
    "astrbot_plugin_zectrix",
    "Zectrix",
    "极趣待办 - 与极趣实验室 AI 待办清单硬件交互，支持待办管理、页面推送",
    "0.1.0",
)
class ZectrixPlugin(star.Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.api_base = config.get("api_base", "https://cloud.zectrix.com/open/v1")
        self.api_key = config.get("api_key", "")
        self.default_device_id = config.get("default_device_id", "")

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    # ===================== zt 命令组 =====================

    @filter.command_group("zt")
    def zt(self):
        pass

    @zt.command("config")
    async def zt_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        # 重新读取配置（用户可能在 WebUI 中修改过）
        self.api_base = self.config.get("api_base", self.api_base)
        self.api_key = self.config.get("api_key", self.api_key)
        self.default_device_id = self.config.get("default_device_id", self.default_device_id)
        masked = (self.api_key[:6] + "****" + self.api_key[-4:]) if len(self.api_key) > 10 else "(未设置)"
        yield event.plain_result(
            "⚙️ 当前配置:\n"
            f"  API 地址: {self.api_base}\n"
            f"  API Key: {masked}\n"
            f"  默认设备: {self.default_device_id or '(未设置)'}\n\n"
            "💡 修改请到 WebUI → 插件管理 → 极趣待办 → 设置"
        )

    @zt.command("devices")
    async def zt_devices(self, event: AstrMessageEvent):
        """查看设备列表"""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.api_base}/devices", headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg', '未知错误')}")
                        return
                    devs = data.get("data", [])
                    if not devs:
                        yield event.plain_result("📭 没有设备")
                        return
                    lines = ["📋 设备列表:"]
                    for d in devs:
                        lines.append(f"  🔹 {d.get('alias', '未命名')} [{d['deviceId']}]")
                    yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @zt.command("help")
    async def zt_help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "🔧 极趣待办 (Zectrix)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ zt config — 查看配置\n"
            "📋 zt devices — 设备列表\n"
            "ℹ️ zt help — 本帮助\n"
            "\n"
            "📝 待办:\n"
            "  todo list\n"
            "  todo add 买牛奶 dueDate=2026-04-15 priority=重要\n"
            "  todo done <ID>\n"
            "  todo del <ID>\n"
            "  todo update <ID> title=新标题\n"
            "\n"
            "📤 推送 (自动使用配置中的默认设备):\n"
            "  push text 今日天气晴 fontSize=24 pageId=1\n"
            "  push structured title=标题 body=正文\n"
            "  push image [pageId] (附带图片)\n"
            "  push clear [pageId]\n"
            "\n"
            "💡 优先级: 普通/重要/紧急\n"
            "   重复: 每天/每周/每月/每年\n"
            "   页面: 1-5"
        )

    # ===================== todo 命令组 =====================

    @filter.command_group("todo")
    def todo(self):
        pass

    @todo.command("list")
    async def todo_list(self, event: AstrMessageEvent, device_id: str = "", status_filter: str = ""):
        """查看待办列表"""
        try:
            params = {}
            did = device_id or self.default_device_id
            if did:
                params["deviceId"] = did
            if status_filter in ("0", "1"):
                params["status"] = status_filter
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.api_base}/todos", headers=self._headers(), params=params) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    todos = data.get("data", [])
                    if not todos:
                        yield event.plain_result("📭 没有待办")
                        return
                    yield event.plain_result("📋 待办列表:\n" + "\n".join(_fmt_todo(t) for t in todos))
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @todo.command("add")
    async def todo_add(self, event: AstrMessageEvent, title: str = "", extra: str = ""):
        """添加待办: todo add 买牛奶 dueDate=2026-04-15 priority=重要"""
        all_text = f"{title} {extra}".strip()
        if not all_text:
            yield event.plain_result("❌ 用法: todo add 买牛奶 dueDate=2026-04-15 priority=重要")
            return
        kv = _parse_kv(all_text)
        if "title" not in kv:
            non_kv = [p for p in all_text.split() if "=" not in p]
            if non_kv:
                kv["title"] = " ".join(non_kv)
        if not kv.get("title"):
            yield event.plain_result("❌ 请提供标题")
            return
        try:
            body = _build_todo_body(kv, self.default_device_id)
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/todos",
                                  headers={**self._headers(), "Content-Type": "application/json"},
                                  data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    d = data.get("data", {})
                    ps = PRIORITY_EMOJI.get(d.get("priority", 0), "")
                    yield event.plain_result(f"✅ [{d.get('id')}] {d.get('title', '')}  {ps}")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @todo.command("done")
    async def todo_done(self, event: AstrMessageEvent, todo_id: str = ""):
        """切换完成状态: todo done <ID>"""
        if not todo_id:
            yield event.plain_result("❌ 用法: todo done <ID>")
            return
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(f"{self.api_base}/todos/{todo_id}/complete", headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    yield event.plain_result(f"✅ 待办 [{todo_id}] 状态已切换")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @todo.command("del")
    async def todo_del(self, event: AstrMessageEvent, todo_id: str = ""):
        """删除待办: todo del <ID>"""
        if not todo_id:
            yield event.plain_result("❌ 用法: todo del <ID>")
            return
        try:
            async with aiohttp.ClientSession() as s:
                async with s.delete(f"{self.api_base}/todos/{todo_id}", headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    yield event.plain_result(f"🗑️ 待办 [{todo_id}] 已删除")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @todo.command("update")
    async def todo_update(self, event: AstrMessageEvent, todo_id: str = "", extra: str = ""):
        """更新待办: todo update <ID> title=新标题 priority=紧急"""
        if not todo_id:
            yield event.plain_result("❌ 用法: todo update <ID> title=新标题")
            return
        kv = _parse_kv(extra)
        if not kv:
            yield event.plain_result("❌ 请提供要更新的字段")
            return
        try:
            body = {}
            for k in ("title", "dueDate", "dueTime"):
                if k in kv:
                    body[k] = kv[k]
            if "desc" in kv:
                body["description"] = kv["desc"]
            if "priority" in kv:
                p = kv["priority"]
                body["priority"] = PRIORITY_MAP.get(p, int(p) if p.isdigit() else 0)
            async with aiohttp.ClientSession() as s:
                async with s.put(f"{self.api_base}/todos/{todo_id}",
                                 headers={**self._headers(), "Content-Type": "application/json"},
                                 data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    d = data.get("data", {})
                    yield event.plain_result(f"✅ [{d.get('id')}] 已更新: {d.get('title', '')}")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    # ===================== push 命令组 =====================

    @filter.command_group("push")
    def push(self):
        pass

    @push.command("text")
    async def push_text(self, event: AstrMessageEvent, *, content: str = ""):
        """推送文本: push text 今日天气晴 fontSize=24 pageId=1"""
        if not content:
            yield event.plain_result("❌ 用法: push text 文本内容 [fontSize=20] [pageId=1]")
            return
        did = self.default_device_id
        if not did:
            yield event.plain_result("❌ 请先在插件设置中配置默认设备 ID")
            return
        try:
            kv = _parse_kv(content)
            text_parts = [p for p in content.split() if "=" not in p]
            body = {"text": " ".join(text_parts)}
            if "fontSize" in kv:
                body["fontSize"] = int(kv["fontSize"])
            if "pageId" in kv:
                body["pageId"] = kv["pageId"]
            if "deviceId" in kv:
                did = kv["deviceId"]
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/devices/{did}/display/text",
                                  headers={**self._headers(), "Content-Type": "application/json"},
                                  data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    d = data.get("data", {})
                    yield event.plain_result(f"✅ 已推送到页面 {d.get('pageId', '?')}")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @push.command("structured")
    async def push_structured(self, event: AstrMessageEvent, *, content: str = ""):
        """推送标题+正文: push structured title=标题 body=正文"""
        did = self.default_device_id
        if not did:
            yield event.plain_result("❌ 请先在插件设置中配置默认设备 ID")
            return
        kv = _parse_kv(content) if content else {}
        body = {}
        if "title" in kv:
            body["title"] = kv["title"]
        if "body" in kv:
            body["body"] = kv["body"]
        if "pageId" in kv:
            body["pageId"] = kv["pageId"]
        if "deviceId" in kv:
            did = kv["deviceId"]
        if not body.get("title") and not body.get("body"):
            yield event.plain_result("❌ 用法: push structured title=标题 body=正文")
            return
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/devices/{did}/display/structured-text",
                                  headers={**self._headers(), "Content-Type": "application/json"},
                                  data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    d = data.get("data", {})
                    yield event.plain_result(f"✅ 已推送到页面 {d.get('pageId', '?')}")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    @push.command("image")
    async def push_image(self, event: AstrMessageEvent, page_id: str = ""):
        """推送图片: push image [pageId]（需附带图片）"""
        did = self.default_device_id
        if not did:
            yield event.plain_result("❌ 请先在插件设置中配置默认设备 ID")
            return
        image_path = None
        try:
            from astrbot.core.message.components import Image as ImageComp
            for comp in event.get_messages():
                if isinstance(comp, ImageComp):
                    image_path = await comp.convert_to_file_path()
                    break
        except Exception:
            pass
        if not image_path:
            yield event.plain_result("❌ 请在命令消息中附带图片")
            return
        try:
            form = aiohttp.FormData()
            with open(image_path, "rb") as f:
                form.add_field("images", f.read(), filename="image.png")
            form.add_field("dither", "true")
            if page_id:
                form.add_field("pageId", page_id)
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/devices/{did}/display/image",
                                  headers=self._headers(), data=form) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    d = data.get("data", {})
                    yield event.plain_result(f"✅ 图片已推送到页面 {d.get('pageId', '?')}")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")
        finally:
            if image_path and os.path.exists(image_path):
                try:
                    if image_path.startswith(tempfile.gettempdir()):
                        os.unlink(image_path)
                except OSError:
                    pass

    @push.command("clear")
    async def push_clear(self, event: AstrMessageEvent, page_id: str = ""):
        """清除页面: push clear [pageId] 不传则清空所有页面"""
        did = self.default_device_id
        if not did:
            yield event.plain_result("❌ 请先在插件设置中配置默认设备 ID")
            return
        try:
            url = f"{self.api_base}/devices/{did}/display/pages"
            if page_id:
                url += f"/{page_id}"
            async with aiohttp.ClientSession() as s:
                async with s.delete(url, headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        yield event.plain_result(f"❌ {data.get('msg')}")
                        return
                    target = f"页面 {page_id}" if page_id else "所有页面"
                    yield event.plain_result(f"🧹 {target} 已清除")
        except Exception as e:
            yield event.plain_result(f"❌ {e}")

    # ===================== LLM 工具（AI 自然语言调用） =====================

    @filter.llm_tool(name="get_devices")
    async def tool_get_devices(self, event: AstrMessageEvent) -> str:
        """获取极趣待办硬件的设备列表，返回所有已绑定设备的名称和ID。"""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.api_base}/devices", headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"获取设备列表失败: {data.get('msg', '未知错误')}"
                    devs = data.get("data", [])
                    if not devs:
                        return "没有找到任何设备"
                    return json.dumps(devs, ensure_ascii=False)
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="get_todos")
    async def tool_get_todos(self, event: AstrMessageEvent, status: str = "", device_id: str = "") -> str:
        """获取待办事项列表，可以按状态和设备过滤。

        Args:
            status(string): 过滤状态，0=待完成，1=已完成，不传=全部
            device_id(string): 设备MAC地址，不传则使用默认设备
        """
        try:
            params = {}
            did = device_id or self.default_device_id
            if did:
                params["deviceId"] = did
            if status in ("0", "1"):
                params["status"] = status
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self.api_base}/todos", headers=self._headers(), params=params) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"获取待办失败: {data.get('msg')}"
                    todos = data.get("data", [])
                    if not todos:
                        return "没有待办事项"
                    return json.dumps(todos, ensure_ascii=False)
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="add_todo")
    async def tool_add_todo(
        self,
        event: AstrMessageEvent,
        title: str,
        due_date: str = "",
        due_time: str = "",
        priority: str = "普通",
        repeat: str = "",
        description: str = "",
    ) -> str:
        """添加一个待办事项。

        Args:
            title(string): 待办标题（必填）
            due_date(string): 截止日期，格式 2026-04-15
            due_time(string): 截止时间，格式 09:00
            priority(string): 优先级，可选: 普通/重要/紧急
            repeat(string): 重复类型，可选: 每天/每周/每月/每年
            description(string): 待办的详细描述
        """
        try:
            body = {"title": title}
            if due_date:
                body["dueDate"] = due_date
            if due_time:
                body["dueTime"] = due_time
            if description:
                body["description"] = description
            body["priority"] = PRIORITY_MAP.get(priority, 0)
            if repeat:
                body["repeatType"] = REPEAT_MAP.get(repeat, "none")
            if self.default_device_id:
                body["deviceId"] = self.default_device_id
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/todos",
                                  headers={**self._headers(), "Content-Type": "application/json"},
                                  data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"添加待办失败: {data.get('msg')}"
                    d = data.get("data", {})
                    return f"已添加待办: [{d.get('id')}] {d.get('title', '')}"
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="complete_todo")
    async def tool_complete_todo(self, event: AstrMessageEvent, todo_id: str) -> str:
        """切换待办的完成状态（完成↔未完成）。

        Args:
            todo_id(string): 待办的数字ID
        """
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(f"{self.api_base}/todos/{todo_id}/complete", headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"操作失败: {data.get('msg')}"
                    return f"待办 [{todo_id}] 状态已切换"
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="delete_todo")
    async def tool_delete_todo(self, event: AstrMessageEvent, todo_id: str) -> str:
        """删除一个待办事项。

        Args:
            todo_id(string): 待办的数字ID
        """
        try:
            async with aiohttp.ClientSession() as s:
                async with s.delete(f"{self.api_base}/todos/{todo_id}", headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"删除失败: {data.get('msg')}"
                    return f"待办 [{todo_id}] 已删除"
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="update_todo")
    async def tool_update_todo(
        self,
        event: AstrMessageEvent,
        todo_id: str,
        title: str = "",
        due_date: str = "",
        due_time: str = "",
        priority: str = "",
        description: str = "",
    ) -> str:
        """更新待办事项的部分字段。

        Args:
            todo_id(string): 待办的数字ID（必填）
            title(string): 新标题
            due_date(string): 新截止日期，格式 2026-04-15
            due_time(string): 新截止时间，格式 09:00
            priority(string): 新优先级，可选: 普通/重要/紧急
            description(string): 新描述
        """
        try:
            body = {}
            if title:
                body["title"] = title
            if due_date:
                body["dueDate"] = due_date
            if due_time:
                body["dueTime"] = due_time
            if description:
                body["description"] = description
            if priority:
                body["priority"] = PRIORITY_MAP.get(priority, 0)
            if not body:
                return "请至少提供一个要更新的字段"
            async with aiohttp.ClientSession() as s:
                async with s.put(f"{self.api_base}/todos/{todo_id}",
                                 headers={**self._headers(), "Content-Type": "application/json"},
                                 data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"更新失败: {data.get('msg')}"
                    d = data.get("data", {})
                    return f"已更新待办: [{d.get('id')}] {d.get('title', '')}"
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="push_text_to_device")
    async def tool_push_text(self, event: AstrMessageEvent, text: str, font_size: int = 20, page_id: str = "") -> str:
        """推送文本内容到待办清单设备的屏幕上。

        Args:
            text(string): 要显示的文本内容
            font_size(number): 字体大小，范围12-48，默认20
            page_id(string): 页面编号1-5
        """
        did = self.default_device_id
        if not did:
            return "未配置默认设备ID，请先在插件设置中配置"
        try:
            body = {"text": text, "fontSize": font_size}
            if page_id:
                body["pageId"] = page_id
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/devices/{did}/display/text",
                                  headers={**self._headers(), "Content-Type": "application/json"},
                                  data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"推送失败: {data.get('msg')}"
                    d = data.get("data", {})
                    return f"文本已推送到设备，页面 {d.get('pageId', '?')}"
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="push_notice_to_device")
    async def tool_push_structured(self, event: AstrMessageEvent, title: str = "", body_text: str = "", page_id: str = "") -> str:
        """推送标题+正文通知到待办清单设备的屏幕上。

        Args:
            title(string): 通知标题
            body_text(string): 通知正文
            page_id(string): 页面编号1-5
        """
        did = self.default_device_id
        if not did:
            return "未配置默认设备ID"
        try:
            body = {}
            if title:
                body["title"] = title
            if body_text:
                body["body"] = body_text
            if page_id:
                body["pageId"] = page_id
            if not body.get("title") and not body.get("body"):
                return "请提供标题或正文"
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/devices/{did}/display/structured-text",
                                  headers={**self._headers(), "Content-Type": "application/json"},
                                  data=json.dumps(body)) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"推送失败: {data.get('msg')}"
                    d = data.get("data", {})
                    return f"通知已推送到设备，页面 {d.get('pageId', '?')}"
        except Exception as e:
            return f"请求失败: {e}"

    @filter.llm_tool(name="push_image_to_device")
    async def tool_push_image(self, event: AstrMessageEvent, image_url: str = "", page_id: str = "") -> str:
        """推送图片到待办清单设备的屏幕上。支持用户直接发送图片或通过URL上传。

        Args:
            image_url(string): 图片的URL链接，如果用户直接发送了图片则不需要此参数
            page_id(string): 页面编号1-5
        """
        did = self.default_device_id
        if not did:
            return "未配置默认设备ID，请先在插件设置中配置"

        image_bytes = None
        filename = "image.png"

        # 方式1：从用户消息中提取直接发送的图片
        try:
            from astrbot.core.message.components import Image as ImageComp
            for comp in event.get_messages():
                if isinstance(comp, ImageComp):
                    image_path = await comp.convert_to_file_path()
                    if image_path and os.path.exists(image_path):
                        with open(image_path, "rb") as f:
                            image_bytes = f.read()
                        filename = os.path.basename(image_path) or "image.png"
                        # 清理临时文件
                        try:
                            if image_path.startswith(tempfile.gettempdir()):
                                os.unlink(image_path)
                        except OSError:
                            pass
                        break
        except Exception:
            pass

        # 方式2：从URL下载图片
        if not image_bytes and image_url:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(image_url) as r:
                        if r.status != 200:
                            return f"下载图片失败，HTTP {r.status}"
                        image_bytes = await r.read()
                        # 从Content-Type推断文件名
                        ct = r.headers.get("Content-Type", "")
                        if "jpeg" in ct or "jpg" in ct:
                            filename = "image.jpg"
                        elif "gif" in ct:
                            filename = "image.gif"
                        elif "webp" in ct:
                            filename = "image.webp"
            except Exception as e:
                return f"下载图片失败: {e}"

        if not image_bytes:
            return "请直接发送一张图片，或提供图片的URL链接"

        # 推送到设备
        try:
            form = aiohttp.FormData()
            form.add_field("images", image_bytes, filename=filename)
            form.add_field("dither", "true")
            if page_id:
                form.add_field("pageId", page_id)
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/devices/{did}/display/image",
                                  headers=self._headers(), data=form) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"推送失败: {data.get('msg')}"
                    d = data.get("data", {})
                    return f"图片已推送到设备，页面 {d.get('pageId', '?')}"
        except Exception as e:
            return f"推送失败: {e}"

    @filter.llm_tool(name="clear_device_screen")
    async def tool_clear_screen(self, event: AstrMessageEvent, page_id: str = "") -> str:
        """清除待办清单设备的屏幕页面内容。

        Args:
            page_id(string): 页面编号1-5，不传则清空所有页面
        """
        did = self.default_device_id
        if not did:
            return "未配置默认设备ID"
        try:
            url = f"{self.api_base}/devices/{did}/display/pages"
            if page_id:
                url += f"/{page_id}"
            async with aiohttp.ClientSession() as s:
                async with s.delete(url, headers=self._headers()) as r:
                    data = await r.json()
                    if data.get("code") != 0:
                        return f"清除失败: {data.get('msg')}"
                    target = f"页面 {page_id}" if page_id else "所有页面"
                    return f"设备的 {target} 已清除"
        except Exception as e:
            return f"请求失败: {e}"
