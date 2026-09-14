type AgentTimelineProps = {
  status: string | null;
  events: { message: string; node: string | null }[];
};

const phases = ['生成并评测初版', '等待人工决策', 'ReAct 工具调用与复评'];

export function AgentTimeline({ status, events }: AgentTimelineProps) {
  const hasHumanDecision = events.some((event) => event.node === 'human_decision');
  const activeIndex = status === 'waiting_for_human' ? 1 : hasHumanDecision && status === 'running' ? 2 : 0;
  return (
    <section className="timeline" aria-label="Agent 执行轨迹">
      <p className="section-kicker">Agent 轨迹</p>
      <ol>
        {phases.map((phase, index) => (
          <li key={phase} className={status && status !== 'completed' && status !== 'failed' && index === activeIndex ? 'is-active' : ''}>
            <span>{index + 1}</span>
            <p>{phase}</p>
          </li>
        ))}
      </ol>
      {status === 'completed' || status === 'failed' || events.length ? <p className="timeline-event">{status === 'completed' ? '任务已完成。' : status === 'failed' ? '任务执行失败，请查看原因。' : events.at(-1)?.message}</p> : null}
    </section>
  );
}
