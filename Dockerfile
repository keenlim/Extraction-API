FROM python:3.11-slim

# Set environment variables 
ENV NLTK_DATA=/nltk

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential libssl-dev libffi-dev python3-dev \
    ffmpeg libsm6 libxext6 poppler-utils libleptonica-dev tesseract-ocr \
    libtesseract-dev python3-pil tesseract-ocr-eng tesseract-ocr-script-latn \
    libreoffice && \
    # Install dependencies
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install "unstructured[csv,doc,docx,pdf,txt,xls,xlsx]" && \
    pip install --no-cache-dir --target . awslambdaric && \
    # Download NLTK data
    # mkdir -p nltk && \
    # chmod 777 nltk && \
    # python -m nltk.downloader -d tmp punkt averaged_perceptron_tagger && \
    # Cleanup build dependencies
    apt-get remove -y curl build-essential libssl-dev libffi-dev python3-dev && \
    apt-get autoremove -y && apt-get autoclean -y

# Set environment variable for NLTK data
ENV NLTK_DATA=/nltk

WORKDIR /app 

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . . 

EXPOSE 8000 

CMD ["uvicorn", "extraction.main:app", "--host", "0.0.0.0", "--port", "8000"]