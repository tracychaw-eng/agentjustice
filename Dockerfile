# AgentBusters FinanceBench Phase-1 Evaluator
# Dockerfile for containerized evaluation runs

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create non-root user to avoid permission issues with mounted volumes
RUN groupadd --gid 1000 evaluator \
    && useradd --uid 1000 --gid 1000 --create-home evaluator

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the repo
COPY --chown=evaluator:evaluator . .

# Create output directories and set ownership
RUN mkdir -p /app/artifacts /app/logs /app/reports \
    && chown -R evaluator:evaluator /app/artifacts /app/logs /app/reports

# Switch to non-root user
USER evaluator

# Default command: run preflight check
CMD ["python", "scripts/run_evaluation.py", "--preflight"]
