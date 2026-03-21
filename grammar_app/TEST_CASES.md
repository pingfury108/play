# 测试用例

## 1. 英文测试

### 测试文本 1（多个错误）
```
Thiss is a testt for grammarr checkingg. He go to school everyday and don't have much time. She writted a letter yesturday.
```

**预期错误**：
- Thiss → This
- testt → test
- grammarr → grammar
- checkingg → checking
- He go → He goes
- everyday → every day
- writted → wrote
- yesturday → yesterday

---

### 测试文本 2（语义错误）
```
The sun rises from the west in the morning. Fish can live on land without water.
```

**预期错误**：
- 太阳从西边升起 → 太阳从东边升起
- 鱼可以在陆地上生活 → 鱼不能在陆地上生活

---

## 2. 中文测试

### 测试文本 3（多个错误）
```
我去学校的路很远，每都天要走一个小时。他昨天吃了一个很的苹果。这个问题的答案很明显。
```

**预期错误**：
- 每都天 → 每天都
- 很的苹果 → 很大的苹果

---

### 测试文本 4（语法错误）
``
我昨天去了图书馆和看书了一下午。这本书非常好看，我看得很快就看完。
```

**预期错误**：
- 和看书了一下午 → 看了一下午书
- 看得很快看完 → 很快就看完了

---

## 3. 标点错误

### 测试文本 5
```
你好吗我很好谢谢，你呢？
```

**预期错误**：
- 你好吗我很好 → 你好吗？我很好
- 谢谢，你呢？ → 谢谢！你呢？

---

## 使用方法

1. 启动服务：
```bash
cd grammar_app
python grammar_app.py
```

2. 访问 http://localhost:5002

3. 复制上面的测试文本到输入框

4. 点击"开始检查"

5. 查看是否所有错误都被标记出来

---

## 优化提示词说明

如果发现某些错误没有被识别，可以尝试以下优化：

1. **增加示例**：在提示词中添加具体的错误示例
2. **分步检查**：要求 AI 分别检查不同类型的错误
3. **降低 temperature**：已经从 0.3 降到 0.2，更稳定
4. **增加 max_tokens**：已经从 2000 增加到 3000，可以返回更多错误
