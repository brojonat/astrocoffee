# Astro Coffee Archive

This project scrapes paper listings from [The Ohio State University's Astronomy Coffee Pages](https://cgi.astronomy.osu.edu/Coffee/Archive/) and serves them using [Datasette](https://datasette.io/).

## Setup

This project uses Python 3.13 or higher.

To install the dependencies, run:

```bash
pip install -e .
```

This will install all the necessary packages listed in `pyproject.toml`.

## Usage

### Scraping the data

You can scrape the data using the `coffee.py` script. This will create or update the `coffee.db` SQLite database file.

To scrape data for a specific date:

```bash
python coffee.py scrape-date --date YYYY-MM-DD
```

To scrape data for a number of days backwards from a certain date (or today):

```bash
python coffee.py scrape-back --start-date YYYY-MM-DD --num-days 10
```

To scrape data for a whole month or multiple months in a given year:

```bash
python coffee.py scrape-month --year 2023 --month 1 --month 2
```

### Serving the data with Datasette

Once you have populated `coffee.db`, you can explore it with Datasette:

```bash
uv run datasette  coffee.db -m metadata.yaml -c datasette.yaml --template-dir templates
```

This will start a web server, typically at `http://127.0.0.1:8001/`. You can open this URL in your browser to view and query the scraped data.
