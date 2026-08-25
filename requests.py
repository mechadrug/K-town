"""小镇请求模型（v5 纵切片：具体请求 = 可游玩的选择）。

首周只围绕三位核心居民：莉娜的干木料、托林的屋顶、梅奶奶的镇志。
选项可以是准备步骤，也可以结束请求；准备步骤不会凭空把请求标成完成，
而是留下关系、场景或次日后果。
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
    effect: str = ""
    progress_delta: int = 0
    closes_request: bool = False
    visible_risk: str = ""
    next_day_observation: str = ""


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
    progress: int = 0
    max_progress: int = 1
    used_options: List[str] = field(default_factory=list)
    observed_option_ids: List[str] = field(default_factory=list)
    next_day_observations: List[str] = field(default_factory=list)
    observed_next_day_observations: List[str] = field(default_factory=list)
    visible_risks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    # 内容归属由篇章导演提供；缺省值保持旧存档/旧调用方兼容。
    chapter_id: str = "week_1_rain"


def seed_initial_requests() -> List[TownRequest]:
    """生成首周三条具体请求；选项效果由 ActionResolver 统一结算。"""
    return [
        TownRequest(
            id="lina_dry_wood",
            requester_id="agent_carpenter",
            location="workshop",
            title="莉娜缺干木料",
            situation="暴雨要来了，木匠莉娜的工坊却断了干木料——湿木料没法用，她的活计停了。",
            deadline=3,
            max_progress=2,
            visible_risks=["去荒野找料会错过在工坊和莉娜规划屋顶的时段"],
            tags=["resident_request", "rain_pressure", "workshop"],
            chapter_id="week_1_rain",
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
                    effect="lina_gather_wood",
                    progress_delta=1,
                ),
                RequestOption(
                    id="share_roof_plan",
                    label="先请莉娜一起规划屋顶",
                    requires="workshop",
                    requires_cn="需要在工坊和莉娜碰面",
                    cost_ap=1,
                    cost_hours=1,
                    result_desc="莉娜摊开草图，和你一起标出最容易漏雨的西侧屋檐。",
                    next_observation="托林听见了这份规划；之后一起修缮会更快。",
                    effect="lina_share_roof_plan",
                    progress_delta=1,
                    visible_risk="你暂时没有带回木料，暴雨前仍需要另找材料。",
                    next_day_observation="工坊墙上多了一张莉娜画的屋顶草图。",
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
                    effect="lina_deliver_wood",
                    closes_request=True,
                    visible_risk="你把时间留给了材料，暂时错过了和莉娜共同规划屋顶。",
                    next_day_observation="莉娜把干木料码在工坊内侧，开始赶工。",
                ),
            ],
        ),
        TownRequest(
            id="torin_roof",
            requester_id="agent_blacksmith",
            location="workshop",
            title="托林的工坊屋顶漏雨",
            situation="托林不愿承认屋顶已经撑不住下一场大雨。现在还能工作，但西侧炉台每隔一会儿就会滴水。",
            deadline=6,
            visible_risks=["临时遮雨能保住今天的炉火，但第二天仍会有滴漏", "正式修好需要更多时间"],
            tags=["resident_request", "rain_pressure", "workshop_roof"],
            chapter_id="week_1_rain",
            options=[
                RequestOption(
                    id="temporary_cover",
                    label="先铺旧布料，做临时遮雨层",
                    requires="workshop",
                    requires_cn="需要在工坊处理漏雨处",
                    cost_ap=2,
                    cost_hours=2,
                    result_desc="你和托林把旧布料钉到西侧屋檐，炉火暂时保住了。雨声却还在布面上敲着。",
                    next_observation="今天工坊能继续工作；明天你会看到遮雨层仍在滴漏。",
                    effect="torin_temporary_cover",
                    closes_request=True,
                    visible_risk="临时层不是正式修缮，第二天仍会滴漏。",
                    next_day_observation="雨停后，旧布料边缘仍在滴漏，往炉台滴水。",
                ),
                RequestOption(
                    id="formal_repair",
                    label="留出时段，直接把屋顶修好",
                    requires="workshop",
                    requires_cn="需要在工坊完成正式修缮",
                    cost_ap=3,
                    cost_hours=3,
                    result_desc="你把时间都留给了屋顶。托林和莉娜一起固定支架，西侧的漏光终于消失。",
                    next_observation="工坊屋顶正式修好，夜里会亮起稳定的窗光。",
                    effect="torin_formal_repair",
                    closes_request=True,
                    visible_risk="这三个时段不能再去荒野或广场传递消息。",
                    next_day_observation="第二天雨声里，工坊没有再传出滴漏声。",
                ),
            ],
        ),
        TownRequest(
            id="mei_town_chronicle",
            requester_id="agent_elder",
            location="square",
            title="梅奶奶想补全镇志",
            situation="归灯集前，梅奶奶想把居民记得的旧事补回镇志。她缺的不是纸，而是有人愿意把听来的话认真带回来。",
            deadline=7,
            visible_risks=["整理镇志会占用你追查旧矿道传闻的时间", "未经核实的说法会留下不同版本"],
            tags=["resident_request", "knowledge", "return_lantern_fair"],
            chapter_id="week_1_rain",
            options=[
                RequestOption(
                    id="listen_to_mei",
                    label="听梅奶奶讲一段旧镇记忆",
                    requires="square",
                    requires_cn="需要在广场和梅奶奶坐下来",
                    cost_ap=1,
                    cost_hours=1,
                    result_desc="梅奶奶翻出一页折角的镇志，慢慢讲起谁曾在暴雨前守住过工坊。",
                    next_observation="你记住了一段可转述的旧事；梅奶奶愿意把缺页交给你保管。",
                    effect="mei_listen_memory",
                    progress_delta=1,
                    next_day_observation="梅奶奶把你的名字写在镇志缺页旁，记下这次谈话的来源。",
                ),
                RequestOption(
                    id="organize_chronicle",
                    label="替她整理一页可信的镇志",
                    requires="square",
                    requires_cn="需要在广场整理镇志",
                    cost_ap=2,
                    cost_hours=2,
                    result_desc="你把能确认来源的说法分门写下，梅奶奶终于补回镇志的一页。",
                    next_observation="镇志多了一页有来源的记录，归灯集准备度也稳了一点。",
                    effect="mei_organize_chronicle",
                    closes_request=True,
                    next_day_observation="广场公告旁贴出了镇志新页，居民开始核对自己的记忆。",
                ),
                RequestOption(
                    id="ask_residents_for_memory",
                    label="替梅奶奶向居民核对传闻",
                    requires="square",
                    requires_cn="需要在广场询问在场居民",
                    cost_ap=2,
                    cost_hours=2,
                    result_desc="你把不同居民的说法并排记下，矛盾没有消失，但大家知道该去哪里核实。",
                    next_observation="旧矿道传闻被标成‘待核实’，不再只是无来源的吓人话。",
                    effect="mei_check_rumor",
                    closes_request=True,
                    visible_risk="你会增加传闻的可见度，却不能保证它是真的。",
                    next_day_observation="旧矿道的公告旁多了一行‘待侦察兵确认’。",
                ),
            ],
        ),
    ]


def seed_chapter_requests(chapter_id: str) -> List[TownRequest]:
    """Return requests for a later chapter without mutating engine state.

    Request options are deliberately declarative.  ``ActionResolver`` checks
    the required location and cost; ``CampaignDirector`` interprets the effect
    id and records the resulting world marker/knowledge/score.
    """

    if chapter_id == "week_2_water":
        return [
            TownRequest(
                id="school_cistern",
                requester_id="agent_healer",
                location="school",
                title="希尔达要清理蓄水槽",
                situation="暴雨留下的泥沙堵住了学校蓄水槽。孩子们还能喝水，但再拖下去就只能依赖商人的高价水桶。",
                deadline=13,
                max_progress=1,
                tags=["chapter_2", "water", "school"],
                chapter_id=chapter_id,
                visible_risks=["用布滤层很快，却不能彻底解决泥沙；彻底清理会占掉一个上午"],
                options=[
                    RequestOption(
                        id="clear_cistern", label="清出蓄水槽里的泥沙", requires="school",
                        requires_cn="需要在学校和希尔达一起清理", cost_ap=2, cost_hours=2,
                        result_desc="你和希尔达把沉在槽底的泥沙一桶桶舀出来，孩子们把干净的石块重新垫好。",
                        next_observation="明天清晨，学校的水面会重新变清。", effect="campaign:water:clear",
                        progress_delta=1, closes_request=True,
                        next_day_observation="学校蓄水槽的水变清了，取水的人不用再排队等商人的水桶。",
                    ),
                    RequestOption(
                        id="cloth_filter", label="先做一层布滤网", requires="school",
                        requires_cn="需要在学校先挡住泥沙", cost_ap=1, cost_hours=1,
                        result_desc="你和希尔达把几层旧布绷在进水口，泥沙少了，蓄水槽暂时还能用。",
                        next_observation="明天还要检查布滤网有没有被新的泥沙压垮。", effect="campaign:water:filter",
                        progress_delta=1, closes_request=True,
                        visible_risk="这是临时办法，下一场大雨仍可能让水槽重新变浑。",
                        next_day_observation="布滤网上积了厚厚一层泥，学校开始寻找更耐用的过滤材料。",
                    ),
                ],
            ),
            TownRequest(
                id="scout_safe_path",
                requester_id="agent_scout",
                location="mine",
                title="罗文要确认旧矿道的路",
                situation="雨季过后，旧矿道里传来新的回声。罗文不想只凭一块旧路牌判断商队能不能走这条近路。",
                deadline=14,
                max_progress=1,
                tags=["chapter_2", "rumor", "mine"],
                chapter_id=chapter_id,
                visible_risks=["相信旧地图会让商队更快抵达，但没有新的安全证据"],
                options=[
                    RequestOption(
                        id="inspect_mine_path", label="陪罗文检查塌方处", requires="mine",
                        requires_cn="需要在矿洞入口确认路况", cost_ap=2, cost_hours=2,
                        result_desc="你和罗文在矿道东侧找到新落下的碎石，把危险路段画进了新的地图。",
                        next_observation="商队会收到一条绕行河谷北坡的可靠建议。", effect="campaign:path:inspect",
                        progress_delta=1, closes_request=True,
                        next_day_observation="矿道口挂起了新的路标，罗文开始教别人辨认松动的岩层。",
                    ),
                    RequestOption(
                        id="trust_old_map", label="按梅奶奶的旧地图走近路", requires="mine",
                        requires_cn="需要在矿洞核对旧地图标记", cost_ap=1, cost_hours=1,
                        result_desc="你把旧地图上的近路重新描了一遍。它仍然能用，但纸边没有任何最近雨季的记录。",
                        next_observation="商队会得到一条更快、却没有经过新检查的路线。", effect="campaign:path:old_map",
                        progress_delta=1, closes_request=True,
                        visible_risk="路线更短，却可能把没有证据的安全感传给外来者。",
                        next_day_observation="罗文在旧地图旁添了一行小字：‘可走，但请先听岩壁的声音。’",
                    ),
                ],
            ),
        ]

    if chapter_id == "week_3_lanterns":
        return [
            TownRequest(
                id="merchant_route",
                requester_id="agent_merchant",
                location="square",
                title="维斯珀要一条能相信的商路",
                situation="商队愿意在归灯集前再来一次，但维斯珀需要知道：镇上是会公开标记风险，还是只把好消息说给外人听。",
                deadline=20,
                max_progress=1,
                tags=["chapter_3", "merchant", "trust"],
                chapter_id=chapter_id,
                visible_risks=["开放集市能带来货物，却会把镇上的短缺也暴露给外来者", "先保镇内库存更稳妥，但商队可能觉得这里不欢迎他们"],
                options=[
                    RequestOption(
                        id="open_market", label="把风险和库存都写在集市牌上", requires="square",
                        requires_cn="需要在广场公开商路信息", cost_ap=2, cost_hours=2,
                        result_desc="你和维斯珀把绕行建议、可交换物资和短缺都写上木牌，商队知道自己要面对什么。",
                        next_observation="明天会有商队回信，决定是否把货车停在广场。", effect="campaign:market:open",
                        progress_delta=1, closes_request=True,
                        next_day_observation="商队在公告旁留下了回信：他们愿意按新路线进镇。",
                    ),
                    RequestOption(
                        id="protect_local_stock", label="先锁住镇内的粮食和药材", requires="square",
                        requires_cn="需要在广场和维斯珀清点库存", cost_ap=1, cost_hours=1,
                        result_desc="你和维斯珀把粮食、药材和灯油分成镇内储备与可交易两栏，先让学校和病人有保障。",
                        next_observation="商队可能不高兴，但镇民会先看到这份清点表。", effect="campaign:market:local",
                        progress_delta=1, closes_request=True,
                        next_day_observation="学校和诊所收到了一份优先领取名单，维斯珀暂时收起了开放集市的招牌。",
                    ),
                ],
            ),
            TownRequest(
                id="school_lanterns",
                requester_id="agent_teacher",
                location="school",
                title="奥尔登要给北路借一盏灯",
                situation="归灯集的北路天黑后没有灯。学校只有一盏旧提灯，矿工戈尔说矿石可以做出更亮的灯芯。",
                deadline=21,
                max_progress=1,
                tags=["chapter_3", "lantern", "school"],
                chapter_id=chapter_id,
                visible_risks=["借走学校的灯会让孩子们少一盏夜读的光", "使用矿石灯火需要有人在危险路段值守"],
                options=[
                    RequestOption(
                        id="lend_school_lamp", label="把学校的旧提灯借给北路", requires="school",
                        requires_cn="需要在学校和奥尔登商量借灯", cost_ap=1, cost_hours=1,
                        result_desc="奥尔登把旧提灯擦亮，写下归还时间，并让高年级孩子轮流记录灯油。",
                        next_observation="今晚北路会亮起来，但学校教室里少了一盏灯。", effect="campaign:lantern:school",
                        progress_delta=1, closes_request=True,
                        next_day_observation="北路的灯按时归还，孩子们把它擦得比原来更亮。",
                    ),
                    RequestOption(
                        id="ask_miner_lantern", label="请戈尔提供矿石灯火", requires="mine",
                        requires_cn="需要去矿洞请戈尔准备灯火", cost_ap=2, cost_hours=2,
                        result_desc="戈尔交出一小袋能稳定发光的矿石，但提醒你：北路必须有人守着，不能把灯丢在那里。",
                        next_observation="北路会有更亮的灯，却也多了一项轮值。", effect="campaign:lantern:mine",
                        progress_delta=1, closes_request=True,
                        next_day_observation="矿石灯火照亮了北路，罗文和戈尔开始排一张夜间轮值表。",
                    ),
                ],
            ),
        ]

    if chapter_id == "week_4_fair":
        return [
            TownRequest(
                id="lantern_fair_council",
                requester_id="agent_elder",
                location="square",
                title="梅奶奶请大家决定归灯集的桌子",
                situation="归灯集终于到了。商队想知道小镇是否欢迎新的交换，居民也想知道这一周的修缮和照顾是不是会被记下来。",
                deadline=28,
                max_progress=1,
                tags=["chapter_4", "festival", "ending"],
                chapter_id=chapter_id,
                visible_risks=["任何选择都会让另一群人少得到一点时间或资源；没有完美答案"],
                options=[
                    RequestOption(
                        id="welcome_caravan", label="请商队和居民坐到同一张桌边", requires="square",
                        requires_cn="需要在广场主持公开的归灯集", cost_ap=2, cost_hours=2,
                        result_desc="你把商队的路线牌、学校的借灯记录和镇志新页放到同一张桌上，先让大家看见事实。",
                        next_observation="归灯集会记住镇上愿意让外来者看到真实情况。", effect="campaign:fair:welcome",
                        progress_delta=1, closes_request=True,
                        next_day_observation="商队在镇志旁留下了下一季的停留日期。",
                    ),
                    RequestOption(
                        id="protect_town_first", label="先让居民把必需品分完再开集市", requires="square",
                        requires_cn="需要在广场完成镇内分配", cost_ap=2, cost_hours=2,
                        result_desc="归灯集先发下水、药材和灯油，商队要等到明天，但镇民不用为必需品竞价。",
                        next_observation="小镇会记住这一晚先照顾谁。", effect="campaign:fair:local",
                        progress_delta=1, closes_request=True,
                        next_day_observation="商队没有立刻离开，维斯珀把明天的货单留在了广场。",
                    ),
                    RequestOption(
                        id="open_council", label="让每个地点派一人公开商议", requires="square",
                        requires_cn="需要在广场召集各处代表", cost_ap=3, cost_hours=3,
                        result_desc="梅奶奶让每个地点派一人发言，争论比预想久，却没有人能把风险藏在自己的抽屉里。",
                        next_observation="归灯集会留下一个由居民轮流维护的公开账本。", effect="campaign:fair:council",
                        progress_delta=1, closes_request=True,
                        next_day_observation="广场的公开账本翻到下一页，居民开始自己记录新的请求。",
                    ),
                ],
            ),
        ]

    return []
