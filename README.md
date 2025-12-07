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

## Loading Data (One-Time Setup)

Before running the application for the first time, you need to load GTFS data into your database:

1. Download GTFS data from [King County Metro GTFS Feed](https://kingcounty.gov/en/dept/metro/travel-options/transit-data/open-data) or obtain it from your data source

2. Create a `data/` folder in the project root and place all GTFS `.txt` files there:
```bash
mkdir data
```

3. Run the data loading script:
```bash
python scripts/load_gtfs_data.py
```

## Running the Application

```bash
streamlit run app/main.py
```

The app will open in your browser at `http://localhost:8501`.
