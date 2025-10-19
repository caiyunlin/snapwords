docker build -t cylin2000/snapwords .
docker run -d -p 8000:8000 --name snapwords_container cylin2000/snapwords
docker push cylin2000/snapwords