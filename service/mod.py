import logging
import grpc
import os
import asyncio
from log import loggers
from minio import Minio
from typing import AsyncGenerator
from parsers import Mime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from parsers import PDFParser, TxtParser, MarkdownParser
from rpc import file_parser_pb2, file_parser_pb2_grpc


logger = loggers("mod", level=logging.INFO)
_thread_pool = ThreadPoolExecutor()


class StorageConfig:
    def __init__(self, storage_type: str, minio_bucket: Optional[str] = None):
        self.storage_type = storage_type
        self.minio_bucket = minio_bucket
        if storage_type == "MINIO":
            self.minio_client = Minio(
                os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY"),
                secret_key=os.getenv("MINIO_SECRET_KEY"),
                secure=False,
            )

    async def download_file(self, file_path: str, local_path: str):
        if self.storage_type == "LOCAL":  # local file
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            if not os.path.isfile(file_path):
                raise IsADirectoryError(f"Path is a directory: {file_path}")
            return file_path
        else:
            try:
                if file_path.startswith("file/"):
                    object_name = file_path
                else:
                    object_name = os.path.basename(file_path)
                    if not object_name:
                        raise ValueError(f"Invalid file path: {file_path}")

                logger.info(
                    f"Downloading from MinIO - bucket: {self.minio_bucket}, object: {object_name}"
                )

                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.minio_client.fget_object(
                        self.minio_bucket, object_name, local_path
                    ),
                )
                return local_path
            except Exception as e:
                logger.error(f"MinIO download error: {e}")
                raise


class FileParser(file_parser_pb2_grpc.FileParserServicer):
    def __init__(self):
        self.initialize()

    def initialize(self):
        from models import ModelLoader

        model_loader = ModelLoader()
        self.pdf_parser = PDFParser(model_loader)

    def _get_mime_from_path(self, file_path: str) -> str:
        """Determine MIME type from file extension"""
        extension = os.path.splitext(file_path)[1].lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".md": "text/markdown",
        }
        return mime_map.get(extension, "application/octet-stream")

    async def parse_pdf(
        self, file_path: str, storage_config: StorageConfig
    ) -> AsyncGenerator[file_parser_pb2.ParseResponse, None]:
        self.pdf_parser.set_storage_config(storage_config)
        async for page_output in self.pdf_parser.process_pdf_files(file_path):
            for item in page_output:
                if item["type"] == "text":
                    response = file_parser_pb2.ParseResponse(
                        text=file_parser_pb2.TextChunk(content=item["text"]),
                        bbox=item["bbox"],
                        pageinfo=file_parser_pb2.PageInfo(
                            width=item["page_size"][1],
                            height=item["page_size"][0],
                            page=item["page"],
                            total=item["total_page"],
                        ),
                        bbox_num=item["bbox_num"],
                    )
                else:
                    type_enum = file_parser_pb2.ImageType.Value(item["type"])
                    response = file_parser_pb2.ParseResponse(
                        image=file_parser_pb2.ImageChunk(
                            file_path=item["file_path"],
                            **{"class": type_enum},
                        ),
                        bbox=item["bbox"],
                        pageinfo=file_parser_pb2.PageInfo(
                            width=item["page_size"][1],
                            height=item["page_size"][0],
                            page=item["page"],
                            total=item["total_page"],
                        ),
                        bbox_num=item["bbox_num"],
                    )
                yield response

    async def parse_txt(
        self, file_path: str, storage_config: StorageConfig
    ) -> AsyncGenerator[file_parser_pb2.ParseResponse, None]:
        parser = TxtParser(storage_config)
        async for response in parser.parse(file_path):
            yield response

    async def parse_markdown(
        self, file_path: str, storage_config: StorageConfig
    ) -> AsyncGenerator[file_parser_pb2.ParseResponse, None]:
        parser = MarkdownParser(storage_config)
        async for response in parser.parse(file_path):
            yield response

    async def Parse(
        self, request: file_parser_pb2.ParseRequest, context: grpc.aio.ServicerContext
    ) -> AsyncGenerator[file_parser_pb2.ParseResponse, None]:
        file_path = request.file_path
        storage_type = request.storage_type
        logger.info(f"Parsing file: {file_path} with storage type: {storage_type}")

        try:
            storage_config = StorageConfig(
                storage_type=file_parser_pb2.StorageType.Name(storage_type),
                minio_bucket=(
                    request.minio_bucket
                    if storage_type == file_parser_pb2.StorageType.MINIO
                    else None
                ),
            )
            try:
                local_path = await storage_config.download_file(file_path, file_path)
                logger.info(f"Using file at path: {local_path}")
            except FileNotFoundError:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"File not found: {file_path}")
                return
            except Exception as e:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error accessing file: {str(e)}")
                return
            self.pdf_parser.set_storage_config(storage_config)
            mime_type = Mime.from_str(self._get_mime_from_path(file_path))
            logger.info(f"Detected MIME type: {mime_type}")

            if mime_type == Mime.Pdf:
                async for response in self.parse_pdf(local_path, storage_config):
                    yield response
                    logger.info("Sent PDF chunk")
            elif mime_type == Mime.Txt:
                async for response in self.parse_txt(local_path, storage_config):
                    yield response
                    logger.info("Sent text chunk")
            elif mime_type == Mime.Md:
                async for response in self.parse_markdown(local_path, storage_config):
                    yield response
                    logger.info("Sent markdown chunk")
            else:
                error_msg = f"Unsupported file type: {mime_type}"
                logger.error(error_msg)
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(error_msg)
                return

            logger.info("File processing completed successfully")

        except Exception as e:
            error_msg = f"An error occurred while parsing the file: {str(e)}"
            logger.exception(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
