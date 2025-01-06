# PDF Watermark Remover

> 该项目所有代码均由*Claude 3.5 Sonnet*生成，包括README

一个功能强大的 PDF 水印去除工具，支持多种处理模式，包括颜色替换和模式匹配。

## 功能特点

- 🎨 颜色替换模式：通过识别和替换特定颜色去除水印
- 🔍 模式匹配模式：基于文本模式和元素特征去除水印
- 📊 页面分析：支持颜色分布和元素结构分析
- 💾 批量处理：支持大文件分批处理
- 🛠️ 可调参数：提供多个可调整参数以优化处理效果
- 🎯 精确控制：支持页面范围控制和处理精度调整

## 安装要求

### 系统要求
- Python 3.7+
- 建议内存：4GB+

### 依赖包
```bash
pip install -r requirements.txt
```

requirements.txt 内容：
```
PyMuPDF>=1.18.0
Pillow>=8.0.0
numpy>=1.19.0
```

## 使用方法

### 1. 颜色分析模式

在处理之前，可以先分析页面的颜色分布：

```bash
python pdf_watermark_remover.py input.pdf --page 0 --color-mode
```

输出示例：
```
页面颜色分析结果:
1. RGB(255,0,0): 5.2%
2. RGB(0,0,0): 85.3%
3. RGB(128,128,128): 9.5%
```

### 2. 颜色替换模式

基本用法：
```bash
python pdf_watermark_remover.py input.pdf \
    --color-mode \
    --colors "255,0,0" \
    --output output.pdf
```

高级用法：
```bash
python pdf_watermark_remover.py input.pdf \
    --color-mode \
    --colors "255,0,0" "0,255,0" \
    --tolerance 0.1 \
    --dpi 200 \
    --batch-size 10 \
    --start-page 0 \
    --end-page 10 \
    --output output.pdf
```

### 3. 模式匹配模式

分析页面元素：
```bash
python pdf_watermark_remover.py input.pdf --page 0
```

添加水印模式：
```bash
python pdf_watermark_remover.py input.pdf \
    --page 0 \
    --add-patterns 1 2 3 \
    --text-patterns "机密" "草稿" "版权" \
    --descriptions "机密水印" "草稿水印" "版权水印" \
    --save-patterns patterns.json
```

使用模式处理：
```bash
python pdf_watermark_remover.py input.pdf \
    --mode pattern \
    --load-patterns patterns.json \
    --output output.pdf
```

## 参数说明

### 基本参数
- `input`: 输入PDF文件路径
- `--output`: 输出PDF文件路径（默认：output.pdf）
- `--page`: 指定要分析的页面编号（从0开始）
- `--start-page`: 处理的起始页码
- `--end-page`: 处理的结束页码

### 颜色模式参数
- `--color-mode`: 启用颜色替换模式
- `--colors`: 要替换的RGB颜色值，格式：R,G,B
- `--tolerance`: 颜色匹配容差（0-1，默认：0.1）
- `--dpi`: 处理图像的DPI值（默认：200）
- `--batch-size`: 批处理大小（默认：10）

### 模式匹配参数
- `--mode pattern`: 使用模式匹配模式
- `--add-patterns`: 要添加的模式元素索引
- `--text-patterns`: 要匹配的文本模式
- `--descriptions`: 模式描述
- `--save-patterns`: 保存模式到JSON文件
- `--load-patterns`: 从JSON文件加载模式

## DPI 参数说明

DPI值会影响处理质量和内存使用：

| DPI值 | 适用场景 | 内存使用（A4每页） | 质量 |
|-------|---------|------------------|------|
| 100 | 大文件，内存受限 | ~0.6MB | 基本 |
| 150 | 普通文件，平衡选择 | ~1.4MB | 良好 |
| 200 | 默认值，推荐选择 | ~2.4MB | 很好 |
| 300 | 高质量需求 | ~5.4MB | 优秀 |
| 600 | 极致质量 | ~21.6MB | 最佳 |

### DPI选择建议

1. 首选200 DPI进行测试
2. 如果效果不理想：
   - 内存充足：提高到300 DPI
   - 内存受限：降低到150 DPI
3. 特殊情况：
   - 处理超大PDF：使用100 DPI
   - 处理细小水印：使用300-600 DPI

## 性能优化建议

### 1. 内存优化
- 降低DPI值
- 减小batch-size
- 使用页面范围分段处理

### 2. 处理速度优化
- 使用较低的DPI值
- 增大batch-size（在内存允许的情况下）
- 减小颜色匹配容差值

### 3. 质量优化
- 增加DPI值
- 调整颜色匹配容差
- 使用多个颜色值精确匹配

## 常见问题

### 1. 内存错误
```
问题：处理时出现内存错误
解决：
- 降低DPI值（如从200降至150）
- 减小batch-size（如从10降至5）
- 分段处理文件
```

### 2. 处理效果不理想
```
问题：水印去除不完全
解决：
- 增加DPI值
- 调整颜色容差
- 添加更多目标颜色值
```

### 3. 处理速度慢
```
问题：处理速度太慢
解决：
- 降低DPI值
- 增大batch-size
- 减小颜色容差值
```

## 注意事项

1. 备份重要文件
2. 先在单页上测试效果
3. 注意内存使用情况
4. 处理大文件时使用分段处理

## 许可证

MIT License

## 贡献指南

欢迎提交Issue和Pull Request！

1. Fork本仓库
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 更新日志

### v1.0.0 (2024-01-06)
- 初始版本发布
- 支持颜色替换模式
- 支持模式匹配模式
- 添加批处理功能
- 添加内存优化功能