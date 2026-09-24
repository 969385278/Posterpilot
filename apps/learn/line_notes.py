"""Small reading aids; these never change or execute repository code."""
FUNCTIONS = {
    '_filter_candidates':'筛选可以用于本次任务的知识卡。',
    '_expand_roles':'把等价的区域名称展开，避免同一含义因为名字不同而漏掉。',
    '_normalize':'统一大小写，移除不参与匹配的标点和空格。',
    '_bigrams':'从每个位置取连续两个字，形成去重集合。',
    'bigram_dice':'比较两段文本共有多少个字对。',
    'hybrid_similarity':'把语义分数和字面分数按比例合在一起。',
    'aggregate_scores':'只用可用的评测信号计算综合分。',
    '_vision_score':'把视觉模型分数换算成最多 35 分。',
    '_attention_score':'按位置比较预测顺序与目标顺序，换算成最多 25 分。',
    'budget_experiment':'模拟模型持续要求工具时，程序怎样控制次数。',
    'revision_experiment':'模拟只返回已经审核、且属于当前活动修订的素材。',
}
PATTERNS = [
    ('requested_roles =', '先展开本次希望匹配的区域名称。'),
    ('review_status == "approved"', '检查这条知识是否已经审核通过。'),
    ('request.include_candidates', '只有明确打开实验开关，才允许候选状态。'),
    ('not card.intents', '卡片未限制用途，或者当前用途在允许列表中，才通过。'),
    ('"any" in', 'any 表示卡片适用于任意区域。'),
    ('intersection(', '求两个集合的共同部分，判断是否存在匹配。'),
    ('expanded.update', '读取等价名称；没有别名时保留原名称。'),
    ('re.sub(', '小写化后，用规则移除不参与比较的字符。'),
    ('index : index + 2', '从当前位置向后取两个字；集合会自动去掉重复字对。'),
    ('left_bigrams =', '先清理左侧文本，再拆成两个字一组。下一步可能进入内部函数。'),
    ('right_bigrams =', '对右侧文本做相同处理，保证比较方式一致。'),
    ('if not left_bigrams', '任何一边没有字对时，不能计算有效的字对相似度。'),
    ('return 2 * overlap', '共同字对数乘二，再除以两边字对数之和。'),
    ('vector_similarity *', '语义占 85%，字面占 15%；最终限制在 0 到 1。'),
    ('hard_rules = max', '从规则满分 40 开始扣除问题惩罚，最低为 0。'),
    ('earned =', '累加已获得的分数。这里临时用 0 求和，但缺失信号本身仍保留 None。'),
    ('available_weight = 40', '规则检查可用，先将分母设为它的权重 40。'),
    ('is not None', '检查是否有结果。真实的 0 分也有结果，不能当成缺失。'),
    ('available_weight += 35', '视觉结果可用，分母加入 35。'),
    ('available_weight += 25', '注意力结果可用，分母加入 25。'),
    ('earned / available_weight', '已获得的分数除以可用权重，归一成百分制并保留两位小数。'),
    ('availability == "unavailable"', '先判断服务结果是否可用；不可用时不参与评分。'),
    ('return None', '返回缺失标记，不是返回真实的零分。'),
    ('vision.score * 0.35', '将视觉分数乘以 35% 的权重。'),
    ('zip(expected_path', '把目标顺序和预测顺序的同一位置配成一对。'),
    ('if expected == actual', '只有同一位置的内容相同，才计为一次匹配。'),
    ('25.0 * overlap', '用匹配比例乘以注意力的满分 25。'),
    ('len(calls) >= limit', '保留限制时，一旦达到工具次数就结束。'),
    ('calls.append', '模拟一次工具尝试，次数增加；没有调用真实模型或工具。'),
    ('not asset["approved"]', '还没审核的草稿先排除。'),
    ('asset["revision"] !=', '检查素材对应的活动修订是否仍为当前修订。'),
    ('visible.append', '只有通过前面所有检查，才把素材加入返回列表。'),
]


def explain(event):
    purpose = FUNCTIONS.get(event['function'], '执行当前函数中的局部逻辑。')
    if event['event'] == 'call':
        return '进入函数，参数已经传入。' + purpose
    if event['event'] == 'return':
        return '函数执行完毕，把右侧返回值交给调用者。' + purpose
    if event['event'] != 'line':
        return event['explanation']
    line = event['code'].strip()
    meaning = next((note for fragment,note in PATTERNS if fragment in line), None)
    if meaning is None:
        if line.startswith('for '): meaning = '逐个查看集合中的元素；每一轮更新当前变量。'
        elif line == 'continue': meaning = '跳过当前元素，继续查看下一个。'
        elif line.startswith('return'): meaning = '计算并返回结果；下一步可以观察真实返回值。'
        elif line.startswith('if '): meaning = '检查条件，决定下一步进入哪个分支。'
        else: meaning = purpose
    return meaning + ' 高亮行即将执行，右侧变量是执行前的值。'
