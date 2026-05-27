@echo off
echo ===================================
echo Along-way MVP Backend Server
echo ===================================
echo.
echo Initializing database and seeding mock data...
python -m app.seed
echo.
echo Starting FastAPI server on http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo.
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
