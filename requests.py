"""小镇请求模型（v5 纵切片：具体请求 = 可游玩的选择）。

首批只实现莉娜「缺干木料」一条线：
- 选项 A：到荒野收集干木料（2 AP / 2 小时）→ 获得 inventory dry_wood
- 选项 B：把干木料送到工坊的莉娜手中（1 AP / 1 小时）→ 请求完成，莉娜关系↑

每个选项必须声明时间/资源成本与前置条件，失败有明确原因。
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class RequestOption:
    id: str
    label: str
    requires: str            # 前置：wilderness（在地点）/ dry_wood（持有物品）/ workshop（在地点）
    requires_cn: str         # 前置的人类可读说明
    cost_ap: int
    cost_hours: int
    result_desc: str
    next_observation: str = ""


@dataclass
class TownRequest:
    id: str
    requester_id: str
    location: str
    title: str
    situation: str
    deadline: int
    status: str = "active"          # active / completed / expired
    options: List[RequestOption] = field(default_factory=list)
    completed_day: int = 0


def seed_initial_requests() -> List[TownRequest]:
    """第 1 天生成的初始请求。请求内容保持少量，纵切片稳定后再扩展。"""
    return [
        TownRequest(
            id="lina_dry_wood",
            requester_id="agent_carpenter",
            location="workshop",
            title="莉娜缺干木料",
            situation="暴雨要来了，木匠莉娜的工坊却断了干木料——湿木料没法用，她的活计停了。",
            deadline=3,
            options=[
                RequestOption(
                    id="gather_wood",
                    label="去荒野收集干木料",
                    requires="wilderness",
                    requires_cn="需要先到荒野",
                    cost_ap=2,
                    cost_hours=2,
                    result_desc="你到荒野挑了些干透的木材，背回工坊的路上雨水渐密。",
                    next_observation="干木料到手了，莉娜在工坊等着这批料。",
                ),
                RequestOption(
                    id="deliver_wood",
                    label="把干木料送到莉娜的工坊",
                    requires="dry_wood",
                    requires_cn="需要持有干木料，且在工坊",
                    cost_ap=1,
                    cost_hours=1,
                    result_desc="你把干木料递给莉娜。她愣了一下，随即笑了：「这料子正合适，暴雨前能赶完这批活。」",
                    next_observation="莉娜的工坊重新转了起来。",
                ),
            ],
        ),
    ]
