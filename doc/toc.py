###
# Code courtesy of Victor S.
# https://towardsdatascience.com/building-a-python-cli-tool-to-extract-the-toc-from-markdown-files-ab5a7b9d07f2/
# https://github.com/CribberSix/markdown-toc-extract


import re
from typing import List, Tuple


def identify_headers(lines: List[str]) -> List[str]:
    # identify header lines of both types
    headers = []
    re_hashtag_headers = r"^#+\ .*$"
    re_alternative_header_lvl1 = r"^=+ *$"
    re_alternative_header_lvl2 = r"^-+ *$"

    for i, line in enumerate(lines):
        # identify headers by leading hashtags
        if re.search(re_hashtag_headers, line):
            headers.append(line)
        # identify alternative headers
        elif re.search(re_alternative_header_lvl1, line):
            # add previous header line with unified h1 format
            headers.append("# " + lines[i - 1])
        elif re.search(re_alternative_header_lvl2, line):
            # add previous header line with unified h2 format
            headers.append("## " + lines[i - 1])
    return headers


def format_header(header: str) -> Tuple[str, int, str]:
    """Calculates the level of the header, removes leading and trailing whitespaces and creates the markdown-link.

    :param header: header line from the markdown file
    :return: a tuple consisting of the cleaned header, the header level and the formatted markdown link.
    """

    # determine the level of the header
    level = 0
    while header[0] == "#":
        level += 1
        header = header[1:]

    # create clickable link by allowing only certain characters,
    # by replacing whitespaces with hyphens and by removing colons
    headerlink = "#" + re.sub(r"[^a-zA-Z0-9 -]", "", header).lower().strip().replace(
        " ", "-"
    ).replace("--", "-")
    return (header.strip(), level, headerlink)


def remove_code_blocks(content: List[str]) -> List[str]:
    """Removes lines starting with "```" (=code blocks) from the markdown file.

    Since code blocks can contain lines with leading hashtags
    (e.g. comments in python) they need to be removed before looking for headers.

    :param content: file contents as a list of strings
    :return: Cleaned file contents as a list of strings
    """
    content_cleaned = []
    code_block = False

    for x in content:
        if x[:3] == "```":
            code_block = not code_block
        elif not code_block:
            content_cleaned.append(x)

    return content_cleaned


def create_toc(toc_levels: List[Tuple[str, int, str]], level_limit: int) -> List[str]:
    """Creates a list of strings representing the items in the table of content.

    :param toc_levels:  A list of Tuples consisting of the header,
                                        the level of the header and a formatted markdown-link to the header.
                        Example for toc_levels:

                                [
                                        ('First Header', 1, '#First-Header')
                                        ('Second level', 2, '#Second-level')
                                        ('First level again', 1, '#First-level-again')
                                ]
    :param level_limit: Limit to the number of levels included in the TOC
    :return: Ordered line items of the table of contents.

    """

    toc = ["# Table of Contents"]
    # create a dict to store the header numbering for each level
    max_header_level = max([x[1] for x in toc_levels]) + 1
    headerlevels = dict.fromkeys(range(1, max_header_level), 1)
    previous_level = 1
    for i, (h, level, link) in enumerate(toc_levels):
        # reset lower header-levels if current header level is higher than prev
        if previous_level > level:
            for x in range(level + 1, previous_level + 1):
                headerlevels[x] = 1

        # construct TOC element
        if level <= level_limit:
            toc.append(
                "\t" * (level - 1) + f"{headerlevels[level]}. [" + h + f"]({link})"
            )

        # increment matching header level
        headerlevels[level] = headerlevels[level] + 1
        previous_level = level
    return toc


def getTOC(data: str, depth=2) -> List[str]:
    content_cleaned = remove_code_blocks(data.split("\n"))

    headers = identify_headers(content_cleaned)

    toc_levels = [format_header(h) for h in headers]

    toc = create_toc(toc_levels, depth)
    return toc
