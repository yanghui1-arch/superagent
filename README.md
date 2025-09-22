# Superagent
The project is for Dass. She is a daily life assistant. The target is to make Dass to be a capable assistant.
Dass can recommend the paper/essay to you, help you code and chat now.  

# Quickstart
```
conda create -n "dass" python=3.12
conda activate dass
pip install -r requirements.txt
```
Expect aboving procedures Dass denpends on Qdrant which is a useful and light-weight vector database. You need to start a `qdrant` docker.
```
docker run -p 6333:6333 qdrant/qdrant:latest
```

The project is at start. You can run script to experience how superagent works.
```
python -m dass.core.agent.dass
```
# Contribution
