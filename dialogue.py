"""K-town 对话系统 —— 语境化 + 关系门控 + 真实后果。

设计依据：docs/product/gameplay-design-v3.md §4.2
- 语境：话题由「性格 × 心情 × 正在做的事 × 关系等级」生成
- 门控：选项随好感解锁（陌生人只能寒暄，朋友能分享秘密）
- 后果：好感变化（有失败率）、知识交换、心情微调（副作用在 api.py 编排）
"""

import random
from typing import Dict, List, Any, Optional


class DialogueSystem:
    """管理玩家与 Agent 之间的对话"""

    def __init__(self):
        self.active_dialogues = {}  # agent_id -> dialogue_state

    def generate_options(self, player, agent, context: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """按关系等级 + 语境生成对话选项"""
        tie = agent.state.social_ties.get(player.identity.id, 0)
        options = []

        # 基础选项（所有人可用）—— 闲聊话题随语境变化
        options.append({
            "id": "chat",
            "text": "闲聊几句",
            "tie_change": 1,
            "success_rate": 0.8,
            "desc": self._chat_topic(agent, context),
            "give_knowledge": True
        })

        # 好感>5 解锁
        if tie > 5:
            options.append({
                "id": "praise",
                "text": "赞美对方",
                "tie_change": 2,
                "success_rate": 0.6,
                "fail_penalty": -1,
                "desc": f"夸夸{agent.identity.name}的工作或性格"
            })

        # 好感>15 解锁
        if tie > 15:
            options.append({
                "id": "ask_skill",
                "text": "请教技能",
                "tie_change": 1,
                "success_rate": 0.5,
                "desc": f"向{agent.identity.name}请教{agent.get_role_cn(agent.identity.role.value)}的心得",
                "give_knowledge": True
            })

        # 好感>30 解锁
        if tie > 30:
            options.append({
                "id": "help",
                "text": "主动帮忙",
                "tie_change": 3,
                "success_rate": 0.7,
                "fail_penalty": -2,
                "desc": f"提出帮{agent.identity.name}完成手头的事",
                "energy_cost": 10
            })

        # 好感>50 解锁
        if tie > 50:
            options.append({
                "id": "share_secret",
                "text": "分享秘密",
                "tie_change": 4,
                "success_rate": 0.8,
                "desc": f"和{agent.identity.name}分享一个自己的秘密",
                "give_knowledge": True
            })

        # 好感<-10 解锁（负面选项）
        if tie < -10:
            options.append({
                "id": "confront",
                "text": "质问对方",
                "tie_change": -2,
                "success_rate": 0.4,
                "fail_penalty": -5,
                "desc": f"质问{agent.identity.name}为什么躲着你"
            })

        return options

    def _chat_topic(self, agent, context: Optional[Dict]) -> str:
        """根据心情/正在做的事/性格生成闲聊话题（对话"有意义"的关键）"""
        ctx = context or {}
        name = agent.identity.name
        mood = ctx.get("mood") or agent.state.mood.value
        task = ctx.get("current_task")
        p = agent.identity.personality

        if mood == "happy":
            return f"看{name}心情很好，聊聊他今天的开心事"
        if mood in ("sad", "anxious", "angry"):
            return f"注意到{name}有些不对劲，试着关心地问问怎么了"
        if task:
            return f"问问{name}正在做的{task}进展如何"
        if p.get("extraversion", 0.5) > 0.6:
            return f"{name}热情地邀请你聊聊镇上的新鲜事"
        return f"和{name}聊聊天气和近况"

    def execute_dialogue(self, player, agent, option: Dict[str, Any],
                         context: Optional[Dict] = None) -> Dict[str, Any]:
        """执行对话，返回结果与后果（tie_change/message/knowledge_gained/mood_effect）"""
        ctx = context or {}
        name = agent.identity.name
        role_cn = agent.get_role_cn(agent.identity.role.value)
        mood = ctx.get("mood") or agent.state.mood.value
        success_rate = option.get("success_rate", 0.7)
        success = random.random() < success_rate

        result = {
            "success": success,
            "tie_change": option.get("tie_change", 1) if success else option.get("fail_penalty", -1),
            "message": "",
            "knowledge_gained": None,
            "mood_effect": 0,          # >0 心情好转, <0 心情变差
        }

        if success:
            result["mood_effect"] = 1
            if option["id"] == "chat":
                msgs = {
                    "happy": [f"{name}笑着和你分享今天的开心事", f"{name}开心地聊起镇上的趣事"],
                    "sad": [f"{name}叹了口气，向你倾诉了一点心事，看起来好受些了", f"{name}谢谢你听他说完"],
                    "anxious": [f"{name}和你聊了聊，紧绷的肩膀放松了一些"],
                    "angry": [f"{name}向你抱怨了几句，慢慢平静下来"],
                    "neutral": [f"{name}平静地和你聊了聊近况", f"{name}和你聊起{role_cn}的工作"],
                }
                result["message"] = random.choice(msgs.get(mood, msgs["neutral"]))
            elif option["id"] == "praise":
                result["message"] = random.choice([f"{name}被你的赞美逗笑了", f"{name}谦虚地说你过奖了"])
            elif option["id"] == "ask_skill":
                result["message"] = random.choice(
                    [f"{name}耐心地教你一些{role_cn}的技巧", f"{name}分享了几条{role_cn}的经验"])
                result["knowledge_gained"] = f"从{name}那里学到了{role_cn}的技巧"
            elif option["id"] == "help":
                result["message"] = random.choice([f"{name}感激地接受了你的帮助", f"{name}和你一起完成了工作"])
            elif option["id"] == "share_secret":
                result["message"] = random.choice(
                    [f"{name}认真地听着，也分享了一个秘密作为交换", f"{name}觉得你们的关系更近了"])
            else:
                result["message"] = f"{name}回应了你的话"
        else:
            if option["id"] == "confront":
                result["mood_effect"] = -1
                result["message"] = random.choice([f"{name}生气地反驳了你", f"{name}冷冷地走开了"])
            else:
                result["message"] = random.choice([f"{name}心不在焉地应付了几句", f"{name}似乎不太想聊"])

        return result

    def get_relationship_level(self, tie: float) -> str:
        """获取关系等级名称"""
        if tie > 70:
            return "知己"
        elif tie > 50:
            return "挚友"
        elif tie > 30:
            return "朋友"
        elif tie > 15:
            return "熟悉"
        elif tie > 5:
            return "认识"
        elif tie > -10:
            return "陌生人"
        else:
            return "敌对"
