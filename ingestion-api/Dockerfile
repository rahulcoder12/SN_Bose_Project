# 1. Use slim Python base
FROM python:3.10-slim

# 2. Prevent Python from buffering stdout
ENV PYTHONUNBUFFERED=1

# 3. Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 4. Set the working directory
WORKDIR /app

# 5. Copy and install dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy application code
COPY . .

# 7. Remove sensitive files that shouldn't be in the image
RUN rm -f .env *.db

# 8. Set correct permissions
RUN chown -R appuser:appuser /app

# 9. Switch to non-root user
USER appuser

# 10. Expose the port
EXPOSE 8000

# 11. Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 12. Run with uvicorn (use multiple workers in production)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]