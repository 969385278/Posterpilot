type PosterPreviewProps = {
  status: string | null;
  initialUrl?: string;
};

export function PosterPreview({ status, initialUrl }: PosterPreviewProps) {
  const running = status === 'running' || status === 'queued';
  const label = status === 'failed' ? '生成未完成' : status === 'waiting_for_human' ? '正在读取海报' : status === 'completed' ? '正在读取结果' : running ? '正在创作中' : '你的海报，从这里开始';
  return (
    <section className="poster-preview" aria-label="海报预览">
      <div className="preview-heading">
        <div>
          <p className="section-kicker">输出预览</p>
          <h2>{label}</h2>
        </div>
        <span className="status-label">{status === 'failed' ? '未完成' : initialUrl ? '初版' : running ? '处理中' : '示例'}</span>
      </div>
      {running && <p className="preview-progress" role="status"><span />正在生成与评测，请稍候</p>}
      {(status !== 'failed' || initialUrl) && <div className="preview-poster-frame">
        <img
          src={initialUrl ?? '/templates/default-poster-portrait.png'}
          alt={initialUrl ? '任务生成的初版海报' : '生成结果出现前的海报示例'}
          width="1080"
          height="1440"
        />
      </div>}
      <p className="preview-note">
        {status === 'failed' ? '本次生成未完成。请查看失败原因，处理后可通过“新建任务”重新提交。系统不会自动重新调用模型；正式环境重新提交可能产生模型费用。' : initialUrl ? '初版已保存。下方会展示优化版和同标准复评结果。' : '完成后，这里会展示初版、优化版、评分和注意力预测结果。'}
      </p>
    </section>
  );
}
