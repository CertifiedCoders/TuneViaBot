FROM nikolaik/python-nodejs:python3.10-nodejs20

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip3 install --no-cache-dir --upgrade pip \
    && pip3 install --no-cache-dir --upgrade -r requirements.txt

CMD bash start
