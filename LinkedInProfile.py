from pathlib import Path
from haystack.components.converters import PyPDFToDocument
import re
from haystack.dataclasses import ByteStream


class LinkedInProfile:
    def __init__(self, pdf_path: str | Path | ByteStream):
        """
        Creates an linkedin object from either path to pdf or bytestream of the pdf.

        Args:
            pdf_path (str | Path | ByteStream): input path or bytestream
        """
        c = PyPDFToDocument()
        if isinstance(pdf_path, str):
            input = [Path(pdf_path)]
        elif isinstance(pdf_path, Path):
            input = [pdf_path]
        else:
            input = [ByteStream(pdf_path)]

        self.profile_raw = c.run(sources=input)["documents"][0].content
        sections = ["Contact", "Top Skills", "Languages", "Summary", "Experience"]
        split_profile = re.split("|".join(sections), self.profile_raw)
        self.profile = {
            "my top skills": split_profile[2].replace("/n", ""),
            "my profile headline": split_profile[3].replace("/n", ""),
            "my profile summary": split_profile[4],
            "my experience": "\n".join(split_profile[5:]),
        }
