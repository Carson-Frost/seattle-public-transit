# Seattle Public Transit Analysis

A Streamlit application for analyzing Seattle public transit data.

## Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Database Connection

Copy `.env.example` to `.env` and update with your database credentials:

```bash
cp .env.example .env
```

## Running the Application

```bash
streamlit run app/main.py
```

The app will open in your browser at `http://localhost:8501`.
