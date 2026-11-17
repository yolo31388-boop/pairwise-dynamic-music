# pairwise-dynamic-music

战斗音乐一进高潮就破音：分层音乐把 stems 直接相加，没有按 bus 做 headroom；横向淡入淡出用固定 0.2 秒，Boss 阶段切换时鼓点被切一半；beat sync 只对齐了循环起点，采样率变化后第 8 小节漂移；ducking 只压音乐总线，语音和 UI 音效没有参与；循环点设在小节中间，crossfade 时多播了一拍；移动端内存不够，所有 stems 一次性解码，切场景卡顿。audio/dynamic_music.py 是核心，tests/test_dynamic_music.py 15个红。要修的是：分层 bus 加 headroom；按 beat 做淡入淡出；采样率重采样后对齐；ducking 全总线；循环点对齐小节；stems 流式加载。

## 运行

```bash
python -m pytest tests -q
```

初始状态：15 个用例失败。修复实现使全部用例通过，不要修改 `tests/` 下的测试。

语言/框架：Python 3, pytest；环境可复现等级：无外部依赖。
