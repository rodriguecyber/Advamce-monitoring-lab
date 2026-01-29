# Docker Lab - Python Flask Application

## Overview
A simple Python Flask web application containerized with Docker. This project demonstrates basic containerization of a Python web service and is ideal for learning Docker fundamentals.

## Project Structure
```
docker-lab/
├── app.py              # Flask application
└── Dockerfile          # Docker image definition
```

## Purpose
This project is a **minimal Flask web service** that:
- Runs a simple HTTP server on port 5000
- Returns "Hello from Docker!" when accessed
- Demonstrates Docker containerization of Python applications

## Key Components

### app.py
- **Framework**: Flask (lightweight Python web framework)
- **Endpoint**: Single route (`/`) that returns a greeting message
- **Server Config**: 
  - Host: `0.0.0.0` (accessible from any network interface)
  - Port: `5000`

### Dockerfile
- **Base Image**: `python:3.9-slim` - Python 3.9 with minimal dependencies
- **Working Directory**: `/app`
- **Dependencies**: Flask installed via pip
- **Exposed Port**: 5000
- **Entry Point**: Runs `python app.py`

## Usage

### Build the Docker Image
```bash
docker build -t docker-lab-flask .
```

### Run the Container
```bash
docker run -p 5000:5000 docker-lab-flask
```

### Access the Application
```bash
curl http://localhost:5000
# Output: Hello from Docker!
```

### Behind a Proxy
This application is will be used with the nginx-proxy project in the labs:
- The nginx proxy (port 80) forwards requests to this Flask app (port 5000)
- Demonstrates multi-container networking and reverse proxy patterns




## Dependencies
- Flask: Web framework for handling HTTP requests
