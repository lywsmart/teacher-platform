import json
import httpx
from fastapi import HTTPException
from app.core.config import get_settings


SYSTEM_PROMPT = """你是一名熟悉中国高校教师成果与职称申报材料写作的专业助手。
你只能依据“事实数据”中的内容归纳和改写。严禁虚构或补充任何论文、课题、比赛、奖项、荣誉、时间、级别、排名、数量和其他事实；不得改变原始事实。不确定的信息不写。表达应正式、客观、清晰。"""


class LLMService:
    def __init__(self):
        self.settings = get_settings()

    async def chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.settings.deepseek_api_key:
            raise HTTPException(503, "尚未配置 DeepSeek API Key")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
                    json={
                        "model": self.settings.deepseek_model,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                )
            if response.status_code in (401, 403):
                raise HTTPException(502, "DeepSeek 鉴权失败，请检查 API Key")
            if response.status_code == 402:
                raise HTTPException(502, "DeepSeek 账户余额不足")
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            if not content:
                raise HTTPException(502, "模型返回内容为空")
            return content
        except HTTPException:
            raise
        except httpx.TimeoutException as exc:
            raise HTTPException(504, "DeepSeek 请求超时") from exc
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise HTTPException(502, "DeepSeek 服务暂时不可用") from exc

    @staticmethod
    def facts_text(profile, achievements) -> str:
        grouped: dict[str, list] = {}
        for item in achievements:
            grouped.setdefault(item.achievement_type, []).append(item)
        lines = [f"教师姓名：{profile.name}", "事实数据（共 %d 项）：" % len(achievements)]
        for kind, items in grouped.items():
            lines.append(f"\n{kind}（{len(items)} 项）：")
            for idx, item in enumerate(items, 1):
                detail = [item.title, str(item.year)]
                if item.level:
                    detail.append(item.level)
                if item.rank:
                    detail.append(f"本人排名第{item.rank}")
                if item.role:
                    detail.append(item.role)
                lines.append(f"{idx}. " + "，".join(detail))
        return "\n".join(lines)

    async def generate_annual_summary(self, profile, achievements, instructions=""):
        facts = self.facts_text(profile, achievements)
        return await self.chat(SYSTEM_PROMPT, f"请生成年度成果总结。{instructions}\n\n{facts}")

    async def generate_title_summary(self, profile, achievements, instructions=""):
        facts = self.facts_text(profile, achievements)
        return await self.chat(SYSTEM_PROMPT, f"请生成适合职称申报的个人业绩总结。{instructions}\n\n{facts}")

    async def generate_category_summary(self, profile, achievements, instructions=""):
        facts = self.facts_text(profile, achievements)
        return await self.chat(SYSTEM_PROMPT, f"请按成果类别归纳总结。{instructions}\n\n{facts}")

    async def rewrite_summary(self, content: str, instructions: str):
        return await self.chat(SYSTEM_PROMPT, f"仅改写下列原文，不添加事实。要求：{instructions}\n\n原文：{content}")
