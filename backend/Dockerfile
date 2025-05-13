# Base Python image
FROM python:3.10

# Install wkhtmltopdf and dependencies
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . /app
WORKDIR /app

# Set the FLASK_APP environment variable
ENV FLASK_APP=app.py

# Expose port 5000
EXPOSE 5000

# Set the entry point
CMD ["flask", "run", "--host=0.0.0.0"]
