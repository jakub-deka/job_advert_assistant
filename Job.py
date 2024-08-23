from multiprocessing import Value
from haystack import component
from haystack import Pipeline
from haystack.dataclasses import ByteStream, Document
from haystack.components.fetchers import LinkContentFetcher
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import re
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from LLM import *


# region components
@component
class HtmlCleaner:
    def __init__(
        self,
        strip_selectors: list[str] = ["script", "style", "link", "noscript"],
        soup_parser: str = "html.parser",
    ):
        self.strip_selectors = strip_selectors
        self.soup_parser = soup_parser

    @component.output_types(htmls=list[str])
    def run(self, htmls: list[ByteStream]):
        res = []
        streams = [s.data.decode() for s in htmls]

        if len(self.strip_selectors) > 0:
            selectors = ",".join(self.strip_selectors)
            for stream in streams:
                soup = BeautifulSoup(stream, self.soup_parser)

                for s in soup.select(selectors):
                    s.extract()
            res.append(str(soup))
        else:
            res = [str(s) for s in streams]

        return {"htmls": res}


@component
class HtmlToMarkdown:
    def __init__(self, md_convert: list[str] | None = None):
        self.md_convert = md_convert

    def convert_html(self, html):
        res = md(html, convert=self.md_convert)
        return res

    @component.output_types(strings=list[str])
    def run(self, htmls: list[str]):
        res = [self.convert_html(s) for s in htmls]
        return {"strings": res}


@component
class RemoveLongStrings:
    def __init__(self, threshold: int = 30):
        self.threshold = threshold

    def remove_string(self, string: str) -> bool:
        if len(string) == 0:
            return True
        elif len(string) >= self.threshold:
            return True
        else:
            return False

    @component.output_types(strings=list[str])
    def run(self, strings: list[str]):
        res = []
        for s in strings:
            remaining_strings = [
                s
                for s in re.split(pattern=r" |\[|\]|\(|\)", string=s)
                if not self.remove_string(s)
            ]
            res.append(" ".join(remaining_strings))

        return {"strings": res}


@component
class StrToDocument:
    @component.output_types(documents=list[Document])
    def run(self, strings: list[str]) -> list[Document]:
        res = [Document(content=s) for s in strings]
        return {"documents": res}


# endregion


class Job:
    def __init__(self, url: str | None = None, job_description: str | None = None):
        if url is not None:
            self._url = url
            pipeline = self.construct_fetch_pipeline()
            self.job_description, self.success = self.run_pipeline(pipeline)
        elif job_description is not None:
            self._url = url
            self.job_description = job_description
            self.success = True
        else:
            raise ValueError(
                "You must either provide job description URL or job description"
            )

    def construct_fetch_pipeline(self):
        fetch_pipeline = Pipeline()
        chrome_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        fetch_pipeline.add_component(
            "fetch", LinkContentFetcher(user_agents=[chrome_user_agent])
        )
        fetch_pipeline.add_component(
            "clean_html",
            HtmlCleaner(strip_selectors=["script", "style", "link", "noscript"]),
        )
        fetch_pipeline.add_component("to_md", HtmlToMarkdown(md_convert=["meta"]))
        fetch_pipeline.add_component(
            "remove_long_strings", RemoveLongStrings(threshold=31)
        )
        fetch_pipeline.add_component("str_to_doc", StrToDocument())
        fetch_pipeline.add_component(
            "clean", DocumentCleaner(remove_repeated_substrings=True)
        )

        fetch_pipeline.connect("fetch", "clean_html")
        fetch_pipeline.connect("clean_html", "to_md")
        fetch_pipeline.connect("to_md", "remove_long_strings")
        fetch_pipeline.connect("remove_long_strings", "str_to_doc")
        fetch_pipeline.connect("str_to_doc", "clean")

        return fetch_pipeline

    def run_pipeline(self, pipeline):
        try:
            success = True
            res = pipeline.run(data={"fetch": {"urls": [self.url]}})["clean"][
                "documents"
            ][0].content
        except Exception as e:
            success = False
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            res = template.format(type(e).__name__, e.args)

        return res, success

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value: str):
        self._url = value
        pipeline = self.construct_fetch_pipeline()
        self.job_description, self.success = self.run_pipeline(pipeline)

    def __str__(self) -> str:
        return json.dumps(
            {
                "url": self.url,
                "job_description": self.job_description,
                "success": self.success,
            }
        )
