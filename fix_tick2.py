with open('tick.py', 'r', encoding='utf-8') as f:
    content = f.read()
old = """    def _load_history(self):
        \"\"\"加载历史每日摘要\"\"\"
        summaries = self.db.get_day_summaries()
        if summaries:
            self.day_summaries = summaries
            self.current_day = summaries[-1]["day"] + 1
            print(f"[OK] 已加载 {len(summaries)} 条历史每日摘要，当前第 {self.current_day} 天")"""
new = """    def _load_history(self):
        \"\"\"加载历史每日摘要\"\"\"
        summaries = self.db.get_day_summaries()
        if summaries:
            self.day_summaries = summaries
            self.current_day = summaries[-1]["day"] + 1
            print(f"[OK] 已加载 {len(summaries)} 条历史每日摘要，当前第 {self.current_day} 天")
        # 初始化当天的agent行为日志
        self.daily_agent_logs = {a.identity.id: [] for a in self.agents}"""
content = content.replace(old, new)
with open('tick.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('修复完成')
