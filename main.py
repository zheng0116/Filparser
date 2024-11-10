import asyncio
import uvloop
import logging
import grpc
import os
from log import loggers
from rpc import file_parser_pb2_grpc
from concurrent import futures
from service import FileParser


asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
logger = loggers("main", level=logging.INFO)
pars_url = os.getenv("PARSER_URL", "0.0.0.0")
pars_port = os.getenv("PARSER_PORT", "50058")


async def serve():
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    file_parser_pb2_grpc.add_FileParserServicer_to_server(FileParser(), server)
    server.add_insecure_port(f"{pars_url}:{pars_port}")
    try:
        await server.start()
        logger.info(f"File Parser Service started on {pars_url}:{pars_port}")
        await server.wait_for_termination()
    except Exception as e:
        logger.error(f"Server encountered an error: {e}")
    finally:
        await server.stop(0)


if __name__ == "__main__":
    asyncio.run(serve())
