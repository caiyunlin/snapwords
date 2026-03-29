# docker
docker build -t cylin2000/snapwords:latest .
docker run -d -p 8000:8000 --name snapwords_container --env-file .env cylin2000/snapwords:latest
docker push cylin2000/snapwords:latest

# local test
uvicorn app.main:app --host 0.0.0.0 --port 8000