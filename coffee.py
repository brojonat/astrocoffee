"""coffee.py"""

import time
import datetime
from typing import Union
import uuid

import bs4
import click
import requests
import sqlite_utils


@click.group()
def cli():
    """CLI entrypoint."""


def format_url(d: datetime.date) -> str:
    """Format the URL for the given date.

    The date of the first brew archive:
    https://cgi.astronomy.osu.edu/Coffee/Archive/2003/January/2003Jan02.html

    """
    return f"https://cgi.astronomy.osu.edu/Coffee/Archive/{d.strftime('%Y/%B/%Y%b%d.html')}"


def _handle_page(
    db: sqlite_utils.Database,
    sd: Union[datetime.date, click.DateTime],
    url: str,
) -> None:
    """Parse the page and extract data."""

    def get_title(b: bs4.element.Tag) -> str:
        try:
            return b.get_text().split("\n")[0]
        except Exception:
            return ""

    def get_authors(b: bs4.element.Tag) -> str:
        try:
            auths = b.get_text().split("\n")[1].split(",")
            return [
                a.strip()
                for a in auths
                if (not a.strip().startswith("et al.")) and (a.strip() != "and")
            ]
        except Exception:
            return ["error fetching authors"]

    def get_links(b: bs4.element.Tag) -> str:
        try:
            links = b.find_all("a")
            return [l["href"] for l in links]
        except Exception:
            return ["error fetching links"]

    res = requests.get(url, timeout=10)
    try:
        res.raise_for_status()
    except requests.HTTPError as exc:
        click.secho(f"Error fetching {url}: {exc}", err=True, fg="red")
        return
    # use lxml because the page is malformed HTML but lxml can handle it
    soup = bs4.BeautifulSoup(res.content, "lxml")

    # The document is actually malformed HTML but since we're using lxml, we can
    # simply find the list items and parse them and we should be fine. If we
    # were to use the html.parser, all the tags would be closed and we'd have to
    # deal with a big glob of text.
    for bullet in soup.find_all("li"):
        try:
            title = get_title(bullet)
            authors = get_authors(bullet)
            links = get_links(bullet)

            db.table("daily").insert(
                {
                    # this needs a single primary key in order to work with m2m
                    "pk": f"{sd} {title}",
                    "date": sd,
                    "title": title,
                    "page_url": url,
                    "err_exception": "",
                    "err_bullet": "",
                },
                column_order=(
                    "date",
                    "title",
                    "page_url",
                ),
                pk="pk",
                replace=True,
            ).m2m(
                "authors",
                [{"author": a} for a in authors],
                pk="author",
            ).m2m(
                "links",
                [{"link": l} for l in links],
                pk="link",
            )
        except Exception as exc:
            db.table("daily").upsert(
                {
                    "date": sd,
                    "page_url": url,
                    "title": f"{uuid.uuid4()}",
                    "err_exception": f"error parsing bullet: {exc}",
                    "err_bullet": f"{bullet}",
                },
                pk=("date", "title"),
            )

    return


@cli.command()
@click.option(
    "--date",
    "-d",
    "sd",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
)
def scrape_date(sd: click.DateTime) -> None:
    # first date
    # https://cgi.astronomy.osu.edu/Coffee/Archive/2003/January/2003Jan02.html
    if sd is None:
        sd = datetime.date.today()
    url = format_url(sd)
    db = sqlite_utils.Database("coffee.db")
    _handle_page(db, sd, url)


@cli.command()
@click.option(
    "--start-date",
    "-s",
    "sd",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
)
@click.option("--num-days", "-n", "num_days", default=1)
def scrape_back(sd: click.DateTime, num_days: int) -> None:
    """Scrape a range of dates."""
    if sd is None:
        sd = datetime.date.today()
    db = sqlite_utils.Database("coffee.db")
    for _ in range(num_days):
        try:
            _handle_page(db, sd, format_url(sd))
        except requests.HTTPError as exc:
            if exc.response.status_code == 404:
                click.secho(f"No data for {sd}", err=True, fg="red")
                continue
            raise exc
        except Exception as exc:
            raise exc
        time.sleep(1)
        sd -= datetime.timedelta(days=1)


@cli.command()
@click.option(
    "--year",
    "-y",
    "year",
    type=click.INT,
    default=datetime.date.today().year,
)
@click.option(
    "--month",
    "-m",
    "months",
    type=click.INT,
    multiple=True,
    default=[datetime.date.today().month],
)
def scrape_month(year, months):
    """Scrape a month of dates."""
    if not months:
        raise ValueError("At least one month is required.")

    for m in months:
        d = datetime.date(year, m, 1)
        db = sqlite_utils.Database("coffee.db")
        base_url = (
            f"https://cgi.astronomy.osu.edu/Coffee/Archive/{d.strftime('%Y/%B')}/"
        )
        soup = bs4.BeautifulSoup(
            requests.get(base_url).content,
            "lxml",
        )
        for a in soup.find_all("a"):
            try:
                _handle_page(
                    db,
                    datetime.datetime.strptime(a.get_text(), "%Y%b%d").strftime(
                        "%Y-%m-%d"
                    ),
                    base_url + a["href"],
                )
            except Exception as exc:
                raise exc
            time.sleep(1)


if __name__ == "__main__":
    cli()
