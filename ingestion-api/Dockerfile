# 1. Use an official, lightweight Python runtime as the base image
FROM python:3.10-slim

# 2. Prevent Python from buffering stdout so logs print immediately in the cloud
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory inside the container
WORKDIR /app

# 4. Copy the requirements file first (this caches dependencies to speed up future builds)
COPY requirements.txt .

# 5. Install the exact dependencies from your local environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of your application code into the container
COPY . .

# 7. Expose the port the FastAPI server will run on
EXPOSE 8000

# 8. Command to run the application (Using 0.0.0.0 allows external cloud access)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]