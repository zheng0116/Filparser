import asyncio
import logging
import os
import cv2
import tempfile
import numpy as np
from log import loggers
from PIL import Image
from minio import Minio
from concurrent.futures import ThreadPoolExecutor
from modules.extract_pdf import load_pdf_fitz
from typing import Union, TypedDict, Literal, Optional, Tuple, List, Dict

logger = loggers("pdf", level=logging.INFO)
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


class TextChunk(TypedDict):
    type: Literal["text"]
    text: str
    bbox: Tuple[int, int, int, int]
    page: int
    page_size: Tuple[int, int]
    total_page: int
    bbox_num: int


class OtherChunk(TypedDict):
    type: Literal["FORMULA", "FIGURE", "TABLE"]
    file_path: str
    bbox: Tuple[int, int, int, int]
    page: int
    page_size: Tuple[int, int]
    total_page: int
    bbox_num: int


Chunk = Union[TextChunk, OtherChunk]


class PDFParser:
    def __init__(self, model_loader):
        self.layout_model = model_loader.layout_model
        self.ocr_model = model_loader.ocr_model
        self.dpi = model_loader.dpi
        self.storage_config = None
        self.image_base_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "images"
        )
        os.makedirs(self.image_base_dir, exist_ok=True)

    def set_storage_config(self, storage_config):
        self.storage_config = storage_config

    @staticmethod
    def merge_ocr_results(ocr_results) -> str:
        merged_text = ""
        for line in ocr_results:
            text, score = line[1]
            merged_text += text
        return merged_text.strip()

    async def save_image(self, image: Image.Image, filename: str) -> str:
        loop = asyncio.get_event_loop()
        if self.storage_config.storage_type == "LOCAL":
            output_path = os.path.join(self.image_base_dir, filename)
            await loop.run_in_executor(_thread_pool, image.save, output_path)
            return output_path
        else:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                await loop.run_in_executor(_thread_pool, image.save, temp_file.name)
                object_name = f"file/{filename}"
                await loop.run_in_executor(
                    _thread_pool,
                    lambda: self.storage_config.minio_client.fput_object(
                        self.storage_config.minio_bucket,
                        object_name,
                        temp_file.name,
                    ),
                )
                os.unlink(temp_file.name)
                return f"{self.storage_config.minio_bucket}/{object_name}"

    async def process_image(
        self,
        image: np.ndarray,
        res: Dict,
        page_idx: int,
        total_page: int,
        bbox_count: int,
    ) -> OtherChunk:
        img_W, img_H = image.shape[:2]
        xmin, ymin = int(res["poly"][0]), int(res["poly"][1])
        xmax, ymax = int(res["poly"][4]), int(res["poly"][5])
        bbox = (xmin, ymin, xmax, ymax)

        category_map: Dict[int, Literal["FIGURE", "TABLE", "FORMULA"]] = {
            3: "FIGURE",
            5: "TABLE",
            8: "FORMULA",
        }
        img_type: Optional[str] = category_map.get(res["category_id"])

        if img_type is None:
            raise ValueError(f"Unsupported category_id: {res['category_id']}")

        img = Image.fromarray(
            cv2.cvtColor(image[ymin:ymax, xmin:xmax], cv2.COLOR_BGR2RGB)
        )

        filename = f"page_{page_idx+1}_{img_type.lower()}_{xmin}_{ymin}.png"
        saved_path = await self.save_image(img, filename)

        return {
            "type": img_type,
            "file_path": saved_path,
            "bbox": bbox,
            "page": page_idx,
            "page_size": (img_W, img_H),
            "total_page": total_page,
            "bbox_num": bbox_count,
        }

    async def process_text(
        self,
        image: np.ndarray,
        pil_img: Image.Image,
        res: Dict,
        page_idx: int,
        total_page: int,
        bbox_count: int,
        lock: asyncio.Lock,
    ) -> Union[TextChunk, None]:
        loop = asyncio.get_event_loop()
        img_W, img_H = image.shape[:2]
        xmin, ymin = int(res["poly"][0]), int(res["poly"][1])
        xmax, ymax = int(res["poly"][4]), int(res["poly"][5])
        crop_box = (xmin, ymin, xmax, ymax)
        cropped_img = Image.new("RGB", pil_img.size, "white")
        cropped_img.paste(pil_img.crop(crop_box), crop_box)
        cropped_img = cv2.cvtColor(np.asarray(cropped_img), cv2.COLOR_RGB2BGR)

        async with lock:
            try:
                ocr_res = await loop.run_in_executor(
                    _thread_pool, lambda: self.ocr_model.ocr(cropped_img)
                )
                ocr_res = ocr_res[0] if ocr_res else None
                if ocr_res:
                    merged_text = self.merge_ocr_results(ocr_res)
                    return {
                        "type": "text",
                        "text": merged_text,
                        "bbox": (xmin, ymin, xmax, ymax),
                        "page": page_idx,
                        "page_size": (img_W, img_H),
                        "total_page": total_page,
                        "bbox_num": bbox_count,
                    }
            except Exception as e:
                logger.error(f"OCR processing error: {e}")
                return None

    def check_bboxes_overlap(
        self, chunks: List[Chunk], overlap_threshold: float = 0.9
    ) -> List[Chunk]:
        def get_overlap(bbox1, bbox2):
            x1 = max(bbox1[0], bbox2[0])
            y1 = max(bbox1[1], bbox2[1])
            x2 = min(bbox1[2], bbox2[2])
            y2 = min(bbox1[3], bbox2[3])

            overlapping_area = max(0, x2 - x1) * max(0, y2 - y1)
            area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
            area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])

            small_area = min(area1, area2)
            if small_area == 0:
                return 0

            return overlapping_area / small_area

        final_output = []
        for i, chunk in enumerate(chunks):
            overlapping = False
            for j, other_chunk in enumerate(final_output):
                if i != j and chunk["type"] == other_chunk["type"]:
                    overlap = get_overlap(chunk["bbox"], other_chunk["bbox"])
                    if overlap > overlap_threshold:
                        overlapping = True
                        break

            if not overlapping:
                final_output.append(chunk)

        return final_output

    async def process_single_page(
        self,
        image: np.ndarray,
        page_idx: int,
        total_page: int,
    ):
        loop = asyncio.get_event_loop()
        lock = asyncio.Lock()

        layout_res = await loop.run_in_executor(
            _thread_pool, lambda: self.layout_model(image, ignore_catids=[15])
        )
        bbox_count = len(
            [res for res in layout_res["layout_dets"] if res["category_id"] != 15]
        )

        chunks = []
        for res in layout_res["layout_dets"]:
            if res["category_id"] in {3, 5, 8}:
                chunk = self.process_image(
                    image,
                    res,
                    page_idx,
                    total_page,
                    bbox_count,
                )
            elif res["category_id"] in {0, 1, 2, 4, 6, 7}:
                pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                chunk = self.process_text(
                    image,
                    pil_img,
                    res,
                    page_idx,
                    total_page,
                    bbox_count,
                    lock,
                )
            else:
                continue
            chunks.append(chunk)

        results = await asyncio.gather(*chunks)
        page_chunk = [result for result in results if result is not None]
        filtered_chunks = self.check_bboxes_overlap(page_chunk, overlap_threshold=0.9)
        return filtered_chunks

    async def process_pdf_files(
        self,
        pdf_path,
    ):
        loop = asyncio.get_event_loop()
        if os.path.isdir(pdf_path):
            all_pdfs = [os.path.join(pdf_path, name) for name in os.listdir(pdf_path)]
        else:
            all_pdfs = [pdf_path]

        for idx, single_pdf in enumerate(all_pdfs):
            try:
                img_list = await loop.run_in_executor(
                    _thread_pool, lambda: load_pdf_fitz(single_pdf, dpi=self.dpi)
                )
            except ZeroDivisionError:
                img_list = None
                print("unexpected pdf file:", single_pdf)
            if img_list is None:
                continue

            total_page = len(img_list)
            for page_idx, image in enumerate(img_list):
                page_output = await self.process_single_page(
                    image,
                    page_idx,
                    total_page,
                )
                yield page_output
