ARG BASE_IMAGE
FROM ${BASE_IMAGE}

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY agent/ agent/
COPY contracts/ contracts/
COPY policies/ policies/

USER 10001
ENTRYPOINT ["python", "-m", "agent.worker"]
