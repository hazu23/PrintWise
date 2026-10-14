"""Start the development server with: python run.py"""
from app import app

if __name__ == "__main__":
    # Debug mode is useful while learning, but should be off on a live website.
    app.run(host="127.0.0.1", port=5000, debug=True)
