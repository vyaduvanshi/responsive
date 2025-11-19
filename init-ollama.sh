#!/bin/sh

#Start Ollama in background
ollama serve &

#Wait for server to start
sleep 10

#Pull the model
echo "Pulling llama3.1:8b model..."
ollama pull llama3.1:8b

#Keep container running
wait