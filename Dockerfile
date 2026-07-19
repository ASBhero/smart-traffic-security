# ==========================================
# STAGE 1: The Builder (Temporary Environment)
# ==========================================
FROM python:3.14-alpine AS builder

WORKDIR /build

# Install the compilers needed to build your wheels
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy your newly fixed requirements file
COPY requirements.txt .

# Compile your Python dependencies into isolated .whl files
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


# ==========================================
# STAGE 2: The Runtime (The Clean Final Image)
# ==========================================
FROM python:3.14-alpine

WORKDIR /app

# Patch the underlying Alpine OS packages and upgrade pip to a secure version
RUN apk update && apk upgrade --no-cache && \
    python -m pip install --no-cache-dir --upgrade pip

# Pull ONLY the pre-compiled Python wheels from Stage 1
COPY --from=builder /build/wheels /app/wheels

# Install the wheels instantly without needing ANY compilers
RUN pip install --no-cache-dir /app/wheels/* && \
    rm -rf /app/wheels

# Copy your actual application source code last
COPY ./app /app

# Make startup script executable
RUN chmod +x /app/startup.sh

EXPOSE 8000
# In production with mTLS, also expose 8443 for TLS
# EXPOSE 8443

CMD ["/bin/sh", "/app/startup.sh"]