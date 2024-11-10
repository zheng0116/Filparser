import yaml
import paddle
from modules.layoutlmv3.model_init import Layoutlmv3_Predictor
from modules.self_modify import ModifiedPaddleOCR


class LayoutModel:
    def __init__(self, weight):
        self.model = Layoutlmv3_Predictor(weight)

    def __call__(self, image, ignore_catids=[]):
        return self.model(image, ignore_catids=ignore_catids)


class OCRModel:
    def __init__(self):
        paddle.set_device("gpu")
        self.model = ModifiedPaddleOCR(show_log=False)

    def ocr(self, image):
        return self.model.ocr(image)


class ModelLoader:
    def __init__(self):
        with open("configs/model_configs.yaml") as f:
            model_configs = yaml.load(f, Loader=yaml.FullLoader)
        self.device: str = model_configs["model_args"]["device"]
        self.dpi: int = model_configs["model_args"]["pdf_dpi"]
        self.layout_model = LayoutModel(model_configs["model_args"]["layout_weight"])
        self.ocr_model = OCRModel()
