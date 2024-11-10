import aiofiles
import logging
from typing import AsyncGenerator
from rpc import file_parser_pb2
from log import loggers

logger = loggers("txt_pars", level=logging.INFO)


class TxtParser:
    @staticmethod
    async def parse(
        file_path: str,
    ) -> AsyncGenerator[file_parser_pb2.ParseResponse, None]:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
            content = await file.read()
        paragraphs = content.split("\n\n")
        total_paragraphs = len(paragraphs)
        for paragraph in paragraphs:
            yield file_parser_pb2.ParseResponse(
                text=file_parser_pb2.TextChunk(content=paragraph),
                bbox=[0],
                pageinfo=file_parser_pb2.PageInfo(
                    width=100, height=100, page=1, total=1
                ),
                bbox_num=total_paragraphs,
            )
