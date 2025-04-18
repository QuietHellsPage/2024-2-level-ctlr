"""
Crawler implementation.
"""

# pylint: disable=too-many-arguments, too-many-instance-attributes, unused-import, undefined-variable, unused-argument
import pathlib
from typing import Pattern, Union
import json
import requests
from core_utils.config_dto import ConfigDTO
import datetime
import re
import os
from bs4 import BeautifulSoup
from core_utils.article.article import Article
from core_utils.constants import ASSETS_PATH, CRAWLER_CONFIG_PATH
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time
import random

class IncorrectSeedURLError(Exception):
    pass

class NumberOfArticlesOutOfRangeError(Exception):
    pass

class IncorrectNumberOfArticlesError(Exception):
    pass

class IncorrectHeadersError(Exception):
    pass

class IncorrectEncodingError(Exception):
    pass

class IncorrectTimeoutError(Exception):
    pass

class IncorrectVerifyError(Exception):
    pass


class Config:
    """
    Class for unpacking and validating configurations.
    """

    def __init__(self, path_to_config: pathlib.Path) -> None:
        """
        Initialize an instance of the Config class.

        Args:
            path_to_config (pathlib.Path): Path to configuration.
        """
        self.path_to_config = path_to_config
        config_content = self._extract_config_content()
        self._seed_urls = config_content.seed_urls
        self._headers = config_content.headers
        self._num_articles = config_content.total_articles
        self._timeout = config_content.timeout
        self._encoding = config_content.encoding
        self.headless_mode = config_content.headless_mode
        self._should_verify_certificate = config_content.should_verify_certificate
        self._validate_config_content()


    def _extract_config_content(self) -> ConfigDTO:
        """
        Get config values.

        Returns:
            ConfigDTO: Config values
        """
        with open(self.path_to_config, "r") as config_file:
            config_content = json.load(config_file)
        return ConfigDTO(**config_content)

    def _validate_config_content(self) -> None:
        """
        Ensure configuration parameters are not corrupt.
        """
        if not isinstance(self._seed_urls, list) or not all(isinstance(url, str) for url in self._seed_urls) or not all(re.compile(r'https?://(www.)?').match(url) for url in self._seed_urls):
            raise IncorrectSeedURLError("Seed URLs have wrong format")

        if not isinstance(self._num_articles, int) or isinstance(self._num_articles, bool) or self._num_articles < 0:
            raise IncorrectNumberOfArticlesError("№ of articles has wrong format or № of articles < 0")

        if self._num_articles > 150:
            raise NumberOfArticlesOutOfRangeError("Number of articles is out of range")

        if not isinstance(self._headers, dict):
            raise IncorrectHeadersError("Headers must be a dict")

        if not isinstance(self._encoding, str):
            raise IncorrectEncodingError("Encoding must be a string")

        if not isinstance(self._timeout, int) or not self._timeout in range(0, 61):
            raise IncorrectTimeoutError("Timeout has wrong format ot timeout is out of range")

        if not isinstance(self.headless_mode, bool):
            raise IncorrectVerifyError("Headless mode has wrong format")
        if not isinstance(self._should_verify_certificate, bool):
            raise IncorrectVerifyError("Verifying has wrong format")

    def get_seed_urls(self) -> list[str]:
        """
        Retrieve seed urls.

        Returns:
            list[str]: Seed urls
        """
        return self._seed_urls

    def get_num_articles(self) -> int:
        """
        Retrieve total number of articles to scrape.

        Returns:
            int: Total number of articles to scrape
        """
        return self._num_articles

    def get_headers(self) -> dict[str, str]:
        """
        Retrieve headers to use during requesting.

        Returns:
            dict[str, str]: Headers
        """
        return self._headers

    def get_encoding(self) -> str:
        """
        Retrieve encoding to use during parsing.

        Returns:
            str: Encoding
        """
        return self._encoding

    def get_timeout(self) -> int:
        """
        Retrieve number of seconds to wait for response.

        Returns:
            int: Number of seconds to wait for response
        """
        return self._timeout

    def get_verify_certificate(self) -> bool:
        """
        Retrieve whether to verify certificate.

        Returns:
            bool: Whether to verify certificate or not
        """
        return self._should_verify_certificate

    def get_headless_mode(self) -> bool:
        """
        Retrieve whether to use headless mode.

        Returns:
            bool: Whether to use headless mode or not
        """
        return self.headless_mode


def make_request(url: str, config: Config) -> requests.models.Response:
    """
    Deliver a response from a request with given configuration.

    Args:
        url (str): Site url
        config (Config): Configuration

    Returns:
        requests.models.Response: A response from a request
    """
    request = requests.get(url, headers=config.get_headers(), timeout=config.get_timeout(), verify=config.get_verify_certificate())

    return request



class Crawler:
    """
    Crawler implementation.
    """

    #: Url pattern
    url_pattern: Union[Pattern, str]

    def __init__(self, config: Config) -> None:
        """
        Initialize an instance of the Crawler class.

        Args:
            config (Config): Configuration
        """
        self.urls = []
        self.config = config


    def _extract_url(self, article_bs: BeautifulSoup) -> str:
        """
        Find and retrieve url from HTML.

        Args:
            article_bs (bs4.BeautifulSoup): BeautifulSoup instance

        Returns:
            str: Url from HTML
        """
        all_posts = article_bs.find(class_="col").find_all(class_="article-middle__media")

        for elem in all_posts:
            link_tag = elem.find('a')

            if link_tag and 'href' in link_tag.attrs:
                link = "https://www.iguides.ru/" + link_tag.get("href")
                if link not in self.urls:
                    return link
        return "EXTRACTION ERROR"

    def find_articles(self) -> None:
        """
        Find articles.
        """
        prepare_environment(ASSETS_PATH)

        driver = webdriver.Chrome()
        driver.get("https://www.iguides.ru/")

        while True:
            try:
                button = [button for button in driver.find_elements(by=By.CLASS_NAME, value="i-btn-loadmore")][0]
                button.click()
                time.sleep(random.randint(3, 10))
            except Exception as e:
                print(e)
                break

        src = driver.page_source
        driver.quit()

        soup = BeautifulSoup(src, "lxml")

        for i in self.get_search_urls():
            try:
                query = make_request(i, self.config)
                if query.status_code != 200:
                    continue
                for _ in range(100):
                    link = self._extract_url(soup)
                    if link == "EXTRACTION ERROR":
                        break
                    if link not in self.urls:
                        self.urls.append(link)
                    if len(self.urls) >= self.config.get_num_articles():
                        break
            except ValueError("ERROR IN find_articles func"):
                continue



    def get_search_urls(self) -> list:
        """
        Get seed_urls param.

        Returns:
            list: seed_urls param
        """
        return self.config.get_seed_urls()


# 10
# 4, 6, 8, 10


class HTMLParser:
    """
    HTMLParser implementation.
    """

    def __init__(self, full_url: str, article_id: int, config: Config) -> None:
        """
        Initialize an instance of the HTMLParser class.

        Args:
            full_url (str): Site url
            article_id (int): Article id
            config (Config): Configuration
        """
        self.config = config
        self.Article = Article(full_url, article_id)


    def _fill_article_with_text(self, article_soup: BeautifulSoup) -> None:
        """
        Find text of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """


    def _fill_article_with_meta_information(self, article_soup: BeautifulSoup) -> None:
        """
        Find meta information of article.

        Args:
            article_soup (bs4.BeautifulSoup): BeautifulSoup instance
        """

    def unify_date_format(self, date_str: str) -> datetime.datetime:
        """
        Unify date format.

        Args:
            date_str (str): Date in text format

        Returns:
            datetime.datetime: Datetime object
        """

    def parse(self) -> Union[Article, bool, list]:
        """
        Parse each article.

        Returns:
            Union[Article, bool, list]: Article instance
        """
        response = make_request(self.Article.url, self.config)
        if response.status_code != 200:
            raise ValueError()


def prepare_environment(base_path: Union[pathlib.Path, str]) -> None:
    """
    Create ASSETS_PATH folder if no created and remove existing folder.

    Args:
        base_path (Union[pathlib.Path, str]): Path where articles stores
    """


def main() -> None:
    """
    Entrypoint for scrapper module.
    """


if __name__ == "__main__":
    main()
