# Smart-Ambulance-Navigation-System

## Steps to perform for Client-Server (FastAPI)

1. Create Virtual environment:
   python -m venv .venv
2. Activate Virtual environment:
   ./.venv/Scripts/activate
3. Install FastAPI:
   pip install "fastapi[standard]"
4. Create requirements.txt file with the following content:
   fastapi==0.115.7
   uvicorn==0.34.0
   typer==0.9.0  
   spaCy==3.7.4
   weasel==0.3.4
5. Install requirements:
   pip install -r requirements.txt
6. To run the script:
   fastapi dev main.py   OR    uvicorn main:app --reload
