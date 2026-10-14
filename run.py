"""Start the development server:  python run.py"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True gives auto-reload and detailed errors for local development only.
    app.run(host="127.0.0.1", port=5000, debug=True)
