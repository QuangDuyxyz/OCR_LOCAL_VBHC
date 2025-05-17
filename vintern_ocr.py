"""
Vintern-1B-v3_5 OCR Module
Cung cấp các hàm cần thiết để xử lý OCR bằng model Vintern-1B-v3_5
"""
import torch
import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from PIL import Image
import os
import numpy as np
import io
from transformers import AutoModel, AutoTokenizer
import logging
import time

# --- CONSTANT ---
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
DEFAULT_MODEL_NAME = "5CD-AI/Vintern-1B-v3_5"
DEFAULT_IMAGE_SIZE = 448
DEFAULT_MAX_BLOCKS = 4

logger = logging.getLogger("VinternOCR")

class VinternOCR:
    """OCR engine using Vintern-1B-v3_5 model"""
    
    def __init__(self, model_name=DEFAULT_MODEL_NAME, use_gpu=True):
        """
        Khởi tạo model Vintern OCR
        
        Args:
            model_name: Tên hoặc đường dẫn đến model
            use_gpu: Có sử dụng GPU hay không
        """
        self.model_name = model_name
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"
        self.dtype = torch.bfloat16 if self.use_gpu else torch.float32
        
        logger.info(f"Khởi tạo Vintern OCR model từ {model_name}")
        logger.info(f"Sử dụng thiết bị: {self.device}")
        
        # Kiểm tra và thông báo tình trạng GPU
        if self.use_gpu:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
            logger.info(f"GPU: {gpu_name}, Memory: {gpu_memory:.2f} GB")
        else:
            logger.warning("Không sử dụng GPU, OCR có thể chậm đáng kể")
        
        self._load_model()
        self._load_tokenizer()
    
    def _load_model(self):
        """Tải model Vintern"""
        start_time = time.time()
        try:
            self.model = AutoModel.from_pretrained(
                self.model_name,
                torch_dtype=self.dtype,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
                use_flash_attn=self.use_gpu,
            ).eval()
            
            if self.use_gpu:
                self.model = self.model.to(self.device)
                
            logger.info(f"Đã tải model thành công trong {time.time() - start_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Lỗi khi tải model: {str(e)}")
            # Thử lại không dùng flash attention
            try:
                self.model = AutoModel.from_pretrained(
                    self.model_name,
                    torch_dtype=self.dtype,
                    low_cpu_mem_usage=True,
                    trust_remote_code=True
                ).eval()
                
                if self.use_gpu:
                    self.model = self.model.to(self.device)
                    
                logger.info(f"Đã tải model (không có flash attention) trong {time.time() - start_time:.2f}s")
            except Exception as e2:
                logger.critical(f"Không thể tải model: {str(e2)}")
                raise RuntimeError(f"Không thể tải model Vintern: {str(e2)}")
    
    def _load_tokenizer(self):
        """Tải tokenizer cho model"""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, 
                trust_remote_code=True, 
                use_fast=False
            )
            logger.info("Đã tải tokenizer thành công")
        except Exception as e:
            logger.critical(f"Không thể tải tokenizer: {str(e)}")
            raise RuntimeError(f"Không thể tải tokenizer: {str(e)}")
    
    def _build_transform(self, input_size):
        """Tạo transform chuẩn bị ảnh cho model"""
        transform = T.Compose([
            T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
            T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
        ])
        return transform
    
    def _find_closest_aspect_ratio(self, aspect_ratio, target_ratios, width, height, image_size):
        """Tìm tỷ lệ khung hình phù hợp nhất"""
        best_ratio_diff = float('inf')
        best_ratio = (1, 1)
        area = width * height
        for ratio in target_ratios:
            target_aspect_ratio = ratio[0] / ratio[1]
            ratio_diff = abs(aspect_ratio - target_aspect_ratio)
            if ratio_diff < best_ratio_diff:
                best_ratio_diff = ratio_diff
                best_ratio = ratio
            elif ratio_diff == best_ratio_diff:
                if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                    best_ratio = ratio
        return best_ratio
    
    def _dynamic_preprocess(self, image, min_num=1, max_num=DEFAULT_MAX_BLOCKS, image_size=DEFAULT_IMAGE_SIZE, use_thumbnail=False):
        """Xử lý ảnh đầu vào thành nhiều khối nhỏ phù hợp với model"""
        orig_width, orig_height = image.size
        aspect_ratio = orig_width / orig_height

        target_ratios = set(
            (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1) for j in range(1, n + 1) if
            i * j <= max_num and i * j >= min_num)
        target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

        target_aspect_ratio = self._find_closest_aspect_ratio(
            aspect_ratio, target_ratios, orig_width, orig_height, image_size)

        target_width = image_size * target_aspect_ratio[0]
        target_height = image_size * target_aspect_ratio[1]
        blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

        resized_img = image.resize((target_width, target_height))
        processed_images = []
        for i in range(blocks):
            box = (
                (i % (target_width // image_size)) * image_size,
                (i // (target_width // image_size)) * image_size,
                ((i % (target_width // image_size)) + 1) * image_size,
                ((i // (target_width // image_size)) + 1) * image_size
            )
            split_img = resized_img.crop(box)
            processed_images.append(split_img)
        if use_thumbnail and len(processed_images) != 1:
            thumbnail_img = image.resize((image_size, image_size))
            processed_images.append(thumbnail_img)
        return processed_images
    
    def _prepare_image(self, image, input_size=DEFAULT_IMAGE_SIZE, max_num=DEFAULT_MAX_BLOCKS):
        """Chuẩn bị ảnh cho model"""
        # Đảm bảo image là đối tượng PIL.Image
        if isinstance(image, str):
            image = Image.open(image).convert('RGB')
        elif isinstance(image, bytes):
            image = Image.open(io.BytesIO(image)).convert('RGB')
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image).convert('RGB')
            
        transform = self._build_transform(input_size=input_size)
        images = self._dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
        pixel_values = [transform(img) for img in images]
        return torch.stack(pixel_values)
    
    def extract_text(self, image, prompt=None):
        """
        Trích xuất text từ ảnh sử dụng model Vintern
        
        Args:
            image: PIL.Image, đường dẫn ảnh, bytes hoặc numpy array
            prompt: Prompt tùy chỉnh, mặc định là trích xuất toàn bộ văn bản
            
        Returns:
            str: Văn bản trích xuất được
        """
        if prompt is None:
            prompt = "<image>\nTrích xuất toàn bộ văn bản có trong hình ảnh bằng tiếng Việt."
            
        try:
            # Ghi log bắt đầu OCR
            start_time = time.time()
            logger.info(f"Bắt đầu OCR với prompt: {prompt[:50]}...")
            
            # Chuẩn bị ảnh đầu vào
            prep_start = time.time()
            pixel_values = self._prepare_image(image, max_num=4)  # Giảm max_num từ 6 xuống 4 để tăng tốc
            prep_time = time.time() - prep_start
            logger.info(f"Chuẩn bị ảnh xong trong {prep_time:.2f}s, blocks: {pixel_values.shape[0]}")
            
            if self.use_gpu:
                pixel_values = pixel_values.to(self.dtype).to(self.device)
            else:
                pixel_values = pixel_values.to(self.dtype)
                
            # Cấu hình sinh văn bản tối ưu hóa
            generation_config = dict(
                max_new_tokens=256,  # Giảm từ 512 xuống 256 để tăng tốc
                do_sample=False,
                num_beams=2,       # Giảm số beams từ 3 xuống 2
                repetition_penalty=3.5,
            )
            
            # Gọi model để sinh văn bản
            inference_start = time.time()
            with torch.no_grad():
                response = self.model.chat(self.tokenizer, pixel_values, prompt, generation_config)
            inference_time = time.time() - inference_start
            
            total_time = time.time() - start_time
            logger.info(f"OCR hoàn thành trong {total_time:.2f}s (inference: {inference_time:.2f}s)")
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất văn bản: {str(e)}")
            logger.exception(e)  # Log stacktrace đầy đủ
            return ""
            
    def extract_text_from_region(self, image, region, prompt=None):
        """
        Trích xuất text từ một vùng cụ thể trong ảnh
        
        Args:
            image: PIL.Image, đường dẫn ảnh, bytes hoặc numpy array
            region: tuple (x1, y1, x2, y2) chỉ định vùng cần trích xuất
            prompt: Prompt tùy chỉnh, mặc định là trích xuất toàn bộ văn bản
            
        Returns:
            str: Văn bản trích xuất được
        """
        try:
            # Nếu image là đường dẫn, đọc ảnh
            if isinstance(image, str):
                image = Image.open(image).convert('RGB')
            elif isinstance(image, bytes):
                image = Image.open(io.BytesIO(image)).convert('RGB')
            elif isinstance(image, np.ndarray):
                image = Image.fromarray(image).convert('RGB')
                
            # Cắt vùng ảnh
            x1, y1, x2, y2 = region
            cropped_image = image.crop((x1, y1, x2, y2))
            
            # Gọi hàm extract_text với vùng đã cắt
            return self.extract_text(cropped_image, prompt)
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất văn bản từ vùng: {str(e)}")
            return ""
    
    def extract_structured_info(self, image, fields=None, prompt=None):
        """
        Trích xuất thông tin có cấu trúc từ ảnh
        
        Args:
            image: PIL.Image, đường dẫn ảnh, bytes hoặc numpy array
            fields: List[str], danh sách các trường thông tin cần trích xuất
            prompt: Prompt tùy chỉnh
            
        Returns:
            dict: Từ điển chứa thông tin đã trích xuất
        """
        if fields is None:
            fields = ["tên văn bản", "số hiệu", "ngày ban hành", "cơ quan ban hành", "người ký"]
            
        if prompt is None:
            field_text = ", ".join(fields)
            prompt = f"<image>\nTrích xuất thông tin từ văn bản trong hình ảnh, bao gồm: {field_text}. Định dạng kết quả theo json."
        
        try:
            # Trích xuất text có cấu trúc
            response = self.extract_text(image, prompt)
            
            # Xử lý kết quả thô (có thể cần thuật toán phức tạp hơn tùy theo đầu ra của model)
            result = {}
            
            # Phân tích kết quả đơn giản
            for field in fields:
                field_lower = field.lower()
                for line in response.split('\n'):
                    if field_lower in line.lower() and ':' in line:
                        key, value = line.split(':', 1)
                        result[field] = value.strip()
                        break
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất thông tin có cấu trúc: {str(e)}")
            return {}
