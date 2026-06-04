# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.12

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app
# Install pip requirements
COPY requirements.txt .
RUN pip3 install -r requirements.txt

WORKDIR /app
COPY socketIO_CoordinationLayer.py ./
COPY openemr/*.py ./openemr/
COPY app/*.py ./app/
COPY app/middleware/*.py ./app/middleware/
COPY app/inference/*.py ./app/inference/
COPY content/* ./content/

EXPOSE 5000

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python3", "socketIO_CoordinationLayer.py"]
