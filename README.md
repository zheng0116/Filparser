# Filparser

A powerful gRPC-based document parsing service that extracts structure and content from various document formats, providing high-performance, scalable document analysis through efficient client-server architecture.

## Models

### LayoutLMv3

Used for PDF document layout detection with following components:

```

0: 'title'              # Title

1: 'plain text'         # Text

2: 'abandon'            # Headers, footers, page numbers, page annotations

3: 'figure'             # Image

4: 'figure_caption'     # Image caption

5: 'table'              # Table

6: 'table_caption'      # Table caption

7: 'table_footnote'     # Table footnote

8: 'isolate_formula'    # Display formula (layout display formula, lower priority than 14)

9: 'formula_caption'    # Display formula label 

13: 'inline_formula'    # Inline formula

14: 'isolated_formula'  # Display formula

15: 'ocr_text'          # OCR result

```

### PaddleOCR

Used for high-accuracy text-chunk recognition and extraction.

## TODO

- Support for more document formats:

- PDF to Markdown conversion

- Enhanced Layout Analysis with `LayoutReader` model


## Quick Start

### Environment Setup

```bash

# Create and activate environment

conda create -n filparser python=3.8

conda activate filparser

```

### Installation

```bash

# Build service

sh run.sh build

# Format code

sh run.sh format

```

### Running the Server

```bash

sh run.sh pdf

```

## Testing

### Local 

```bash

grpcurl \
    --import-path ./ \
    --proto ./file_parser.proto \
    -d '{"file_path": "./2.pdf", "storage_type": "LOCAL"}' \
    -emit-defaults \
    --plaintext 127.0.0.1:50058 file_parser.FileParser.Parse

```

### MinIO 

```bash

grpcurl \
    --import-path ./ \
    --proto ./file_parser.proto \
    -d '{"file_path": "file/1.pdf", "storage_type": "MINIO", "minio_bucket": "test"}' \
    -emit-defaults \
    --plaintext 127.0.0.1:50058 file_parser.FileParser/Parse

```

## License
This project is open-sourced under the [AGPL-3.0](LICENSE) license.
## Acknowledgement
   - [PDF-Extract-Kit](https://github.com/opendatalab/PDF-Extract-Kit): PDF parsing 
   - [LayoutLMv3](https://github.com/microsoft/unilm/tree/master/layoutlmv3): Layout detection model
   - [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR): OCR model
