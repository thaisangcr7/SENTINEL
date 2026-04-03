# Dockerfile — Instructions for building the SENTINEL container image
#
# A Docker image is a snapshot of an environment: OS + Python + your code + dependencies.
# When you run the image, it becomes a container — a live, isolated process.
#
# Think of it like a recipe:
#   Dockerfile = the recipe
#   docker build = cooking the recipe → produces an "image" (the finished dish)
#   docker run   = serving the dish → produces a "container" (the running instance)
#
# Every line below is a LAYER. Docker caches each layer.
# If nothing changed in that layer, Docker skips it on the next build.
# This is why order matters — put things that change rarely at the top.

# Pattern: Base Image
# FROM tells Docker what to start with. We don't start from scratch —
# we start from an existing Python image that already has Python 3.11 installed.
# "slim" = a minimal Debian Linux with just enough to run Python. No bloat.
# This gives us a consistent Python version on every machine — your Mac, CI, EC2.
FROM python:3.11-slim

# Pattern: Working Directory
# WORKDIR sets the folder all subsequent commands run from inside the container.
# If the folder doesn't exist, Docker creates it.
# /app is the convention — short, simple, obvious.
WORKDIR /app

# Pattern: Dependency caching (the key Docker optimization)
# Copy ONLY requirements.txt first — before copying any app code.
# WHY: Docker caches each layer. If requirements.txt hasn't changed,
# Docker reuses the cached pip install layer and skips it entirely.
# If we copied all files first, any code change would invalidate this cache
# and reinstall ALL packages every build. This trick saves minutes per build.
COPY requirements.txt .

# RUN executes a shell command during the build (not at runtime).
# --no-cache-dir = don't save the pip download cache inside the image (smaller image size).
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application code.
# Done AFTER pip install so code changes don't bust the dependency cache.
COPY . .

# Pattern: Exposed Port (documentation only)
# EXPOSE tells readers which port the app listens on.
# It does NOT actually open the port — docker-compose handles that.
EXPOSE 8000

# Pattern: CMD (the default command when the container starts)
# This is what runs when someone does "docker run" or "docker-compose up".
# Using array form ["uvicorn", ...] instead of a string — best practice because
# it runs uvicorn directly instead of inside a shell process.
# --host 0.0.0.0 = listen on all network interfaces, not just localhost.
#   Without this, the container runs but nothing outside it can connect.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
