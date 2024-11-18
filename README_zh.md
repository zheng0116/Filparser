# Filparser
## 🌟 概述
Filparser 是一个基于 gRPC 的强大文档解析服务，能够从各种文档格式中提取结构和内容。它不仅提供高性能、可扩展的文档分析能力，还支持基于文档版面的智能分块功能，可直接为检索增强生成（RAG）系统提供高质量的文本块。

## 🚀 模型

### LayoutLMv3

用于 PDF 文档版面检测，包含以下组件：

```
0: 'title',              # 标题
1: 'plain text',         # 正文
2: 'abandon',            # 包括页眉、页脚、页码和页面注释
3: 'figure',             # 图片
4: 'figure_caption',     # 图片说明
5: 'table',              # 表格
6: 'table_caption',      # 表格标题
7: 'table_footnote',     # 表格脚注
8: 'isolate_formula',    # 显示公式（这是版面显示公式，优先级低于14）
9: 'formula_caption',    # 显示公式标签
13: 'inline_formula',    # 行内公式
14: 'isolated_formula',  # 显示公式
15: 'ocr_text'           # OCR结果
```

### PaddleOCR

用于高精度文本块识别和提取。

## 待办事项

- 支持更多文档格式
- PDF 转 Markdown 功能
- 使用 `LayoutReader` 模型增强版面分析能力

## 快速开始

### 环境配置

```bash
# 创建并激活环境
conda create -n filparser python=3.8
conda activate filparser
```

### 安装

```bash
# 构建grpc服务
sh run.sh build
# 格式化代码
sh run.sh format
```

### 运行服务

```bash
sh run.sh pdf
```

## 测试

### 本地测试

```bash
grpcurl \
    --import-path ./ \
    --proto ./file_parser.proto \
    -d '{"file_path": "./2.pdf", "storage_type": "LOCAL"}' \
    -emit-defaults \
    --plaintext 127.0.0.1:50058 file_parser.FileParser.Parse
```

### MinIO 测试

```bash
grpcurl \
    --import-path ./ \
    --proto ./file_parser.proto \
    -d '{"file_path": "file/1.pdf", "storage_type": "MINIO", "minio_bucket": "test"}' \
    -emit-defaults \
    --plaintext 127.0.0.1:50058 file_parser.FileParser/Parse
```

## 许可证

本项目采用 [AGPL-3.0](LICENSE) 许可证开源。

## 致谢

- [PDF-Extract-Kit](https://github.com/opendatalab/PDF-Extract-Kit)：PDF解析
- [LayoutLMv3](https://github.com/microsoft/unilm/tree/master/layoutlmv3)：布局检测模型
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)：OCR 模型