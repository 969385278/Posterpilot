type AttentionMapProps = {
  imageUrl?: string;
  availability: string;
};

export function AttentionMap({ imageUrl, availability }: AttentionMapProps) {
  const synthetic = import.meta.env.VITE_POSTERPILOT_DEMO === 'true';
  if (!imageUrl) {
    return (
      <section className="attention-map" aria-label="注意力预测">
        <p className="section-kicker">注意力预测</p>
        <p>DeepGaze 当前不可用，未生成热力图。</p>
      </section>
    );
  }
  return (
    <section className="attention-map" aria-label="注意力预测">
      <p className="section-kicker">注意力预测</p>
      <img src={imageUrl} alt={synthetic ? '离线合成注意力测试图' : 'DeepGaze 预测的视觉注意力热力图'} />
      <p>{synthetic ? '这是合成测试图片，不是 DeepGaze 预测，仅用于验证页面。' : `状态：${availability}。这是模型预测，不是真实用户眼动。`}</p>
    </section>
  );
}
