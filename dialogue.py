"""K-town 对话系统模块"""
import random
from typing import Dict, List, Any, Optional


class DialogueSystem:
    """管理Agent之间的对话"""
    
    def __init__(self):
        self.active_dialogues = {}  # agent_id -> dialogue_state
    
    def generate_options(self, player, agent) -> List[Dict[str, Any]]:
        """根据关系等级生成对话选项"""
        tie = agent.state.social_ties.get(player.identity.id, 0)
        options = []
        
        # 基础选项（所有人可用）
        options.append({
            "id": "chat",
            "text": "闲聊几句",
            "tie_change": 1,
            "success_rate": 0.8,
            "desc": "随便聊聊天气和近况"
        })
        
        # 好感>5解锁
        if tie > 5:
            options.append({
                "id": "praise",
                "text": "赞美对方",
                "tie_change": 2,
                "success_rate": 0.6,
                "fail_penalty": -1,
                "desc": "夸奖对方的工作或性格"
            })
        
        # 好感>15解锁
        if tie > 15:
            options.append({
                "id": "ask_skill",
                "text": "请教技能",
                "tie_change": 1,
                "success_rate": 0.5,
                "desc": "向对方学习一些技能",
                "give_knowledge": True
            })
        
        # 好感>30解锁
        if tie > 30:
            options.append({
                "id": "help",
                "text": "主动帮忙",
                "tie_change": 3,
                "success_rate": 0.7,
                "fail_penalty": -2,
                "desc": "提出帮助对方完成工作",
                "energy_cost": 10
            })
        
        # 好感>50解锁
        if tie > 50:
            options.append({
                "id": "share_secret",
                "text": "分享秘密",
                "tie_change": 4,
                "success_rate": 0.8,
                "desc": "分享一个自己的秘密",
                "give_knowledge": True
            })
        
        # 好感<-10解锁（负面选项）
        if tie < -10:
            options.append({
                "id": "confront",
                "text": "质问对方",
                "tie_change": -2,
                "success_rate": 0.4,
                "fail_penalty": -5,
                "desc": "质问对方为什么不喜欢你"
            })
        
        return options
    
    def execute_dialogue(self, player, agent, option: Dict[str, Any]) -> Dict[str, Any]:
        """执行对话，返回结果"""
        import random
        
        success_rate = option.get("success_rate", 0.7)
        success = random.random() < success_rate
        
        result = {
            "success": success,
            "tie_change": option.get("tie_change", 1) if success else option.get("fail_penalty", -1),
            "message": "",
            "knowledge_gained": None
        }
        
        if success:
            if option["id"] == "chat":
                messages = [
                    f"{agent.identity.name}微笑着和你聊了聊最近的天气",
                    f"{agent.identity.name}分享了一些小镇的趣事",
                    f"{agent.identity.name}和你聊了聊工作的心得"
                ]
            elif option["id"] == "praise":
                messages = [
                    f"{agent.identity.name}被你的赞美逗笑了",
                    f"{agent.identity.name}谦虚地说你过奖了",
                    f"{agent.identity.name}开心地聊了起来"
                ]
            elif option["id"] == "ask_skill":
                messages = [
                    f"{agent.identity.name}耐心地教你一些技巧",
                    f"{agent.identity.name}分享了一些工作经验",
                    f"{agent.identity.name}演示了一些操作要领"
                ]
                result["knowledge_gained"] = f"从{agent.identity.name}那里学到了新技能"
            elif option["id"] == "help":
                messages = [
                    f"{agent.identity.name}感激地接受了你的帮助",
                    f"{agent.identity.name}和你一起完成了工作",
                    f"{agent.identity.name}说有你帮忙轻松多了"
                ]
            elif option["id"] == "share_secret":
                messages = [
                    f"{agent.identity.name}认真地听着你的分享",
                    f"{agent.identity.name}也分享了一个秘密作为交换",
                    f"{agent.identity.name}觉得你们的关系更近了"
                ]
            else:
                messages = [f"{agent.identity.name}回应了你的话"]
            result["message"] = random.choice(messages)
        else:
            if option["id"] == "chat":
                messages = [
                    f"{agent.identity.name}心不在焉地应付了几句",
                    f"{agent.identity.name}似乎不太想聊天"
                ]
            elif option["id"] == "praise":
                messages = [
                    f"{agent.identity.name}觉得你的赞美有点虚伪",
                    f"{agent.identity.name}尴尬地转移了话题"
                ]
            elif option["id"] == "confront":
                messages = [
                    f"{agent.identity.name}生气地反驳了你",
                    f"{agent.identity.name}冷冷地走开了"
                ]
            else:
                messages = [f"{agent.identity.name}对你的提议不感兴趣"]
            result["message"] = random.choice(messages)
        
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
