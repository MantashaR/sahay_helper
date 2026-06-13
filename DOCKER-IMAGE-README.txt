Sahay — portable Docker image
==============================

FILE:  sahay-image.tar   (~101 MB, multi-architecture: linux/amd64 + linux/arm64)

This single file runs on Windows, macOS (Intel AND Apple Silicon), and Linux —
anywhere Docker is installed. No internet, no build, no Python setup needed.


HOW TO USE (on any machine with Docker)
----------------------------------------
1. Copy sahay-image.tar to the target machine.

2. Load the image into Docker:

       docker load -i sahay-image.tar

   (prints: "Loaded image: sahay:latest")

3. Run it:

       docker run -d -p 5000:5000 --name sahay sahay:latest

4. Open in a browser:

       http://localhost:5000


MANAGE
------
Stop:     docker stop sahay
Start:    docker start sahay
Remove:   docker rm -f sahay
Logs:     docker logs sahay


OPTIONAL — real Hindi/Tamil/Bengali translation (Claude API)
------------------------------------------------------------
Runs fully offline by default. To enable AI translation, pass a key:

       docker run -d -p 5000:5000 -e ANTHROPIC_API_KEY=sk-ant-... --name sahay sahay:latest


NOTES
-----
- Docker automatically picks the matching CPU architecture (amd64 / arm64).
- Port 5000 in use? Map a different host port:  -p 8080:5000  then open localhost:8080
- The image excludes all secrets and the unrelated byoc-workshop-template folder.
