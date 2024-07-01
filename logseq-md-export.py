#!/usr/bin/env python3
import re
import os
import shutil
from enum import Enum
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('logseq_file', type=str)
parser.add_argument('output_path', type=str)
args = parser.parse_args()

class LineType(Enum):
    TITLE = 1
    LIST = 2
    QUOTE = 3
    CODE_BLOCK_MARKER = 4
    CODE = 5
    EMPTY = 6
    TEXT = 7

class LineHierarchy(Enum):
    PARENT = 1
    CHILD = 2

class State(Enum):
    CLEAR = 1
    TRAVERSING_CODE_BLOCK = 2
    TRAVERSING_MULTILINE = 3


output_project_path = os.path.join(args.output_path, os.path.basename(args.logseq_file))
try:
    os.mkdir(output_project_path)
except FileExistsError:
    pass
out = open(os.path.join(output_project_path, os.path.basename(args.logseq_file)), "w")
file = open(args.logseq_file, "r")
lines_raw = file.readlines()

def get_file_info(file_path):
    abs_path = os.path.abspath(file_path)
    os.path.basename(abs_path)

def import_asset(filename, subdir=""):
    logseq_file_base_dir = os.path.dirname(os.path.abspath(args.logseq_file))
    try:
        os.mkdir(os.path.join(output_project_path, "assets"))
    except FileExistsError:
        pass
    shutil.copy(os.path.join(logseq_file_base_dir, "..", "assets", subdir, filename), os.path.join(output_project_path, "assets", filename))

def get_line_type(line):
    L1_tag = line_content_raw[0]
    L2_tag = line_content_raw[2] if len(line_content_raw) > 2 else None

    if L1_tag == "#":
        return LineType.TITLE, LineHierarchy.PARENT
    
    if L2_tag is None:
        if L1_tag == "-":
            # empty line on a list
            return LineType.EMPTY, LineHierarchy.PARENT
        elif L1_tag == " ":
            # empty line on a multi-line block
            return LineType.EMPTY, LineHierarchy.CHILD
        else:
            print("PARSING ERROR AT LINE:", line)
            exit(1)
    if L2_tag == " ":
        # this must be part of a multi-line content block
        return LineType.TEXT, LineHierarchy.CHILD
    elif L2_tag == ">":
        if L1_tag == "-":
            return LineType.QUOTE, LineHierarchy.PARENT
        else:
            return LineType.QUOTE, LineHierarchy.CHILD
    elif L2_tag == "#":
        # titles an only be parent. If this is not, it's not a title!
        if L1_tag == "-":
            return LineType.TITLE, LineHierarchy.PARENT
        elif L1_tag == " ":
            return LineType.TEXT, LineHierarchy.CHILD
        else:
            print("PARSING ERROR AT LINE:", line)
            exit(1)
    elif L2_tag == "`":
        parent_code_block = re.search("^(\t*)- (```)", line)
        child_code_block = re.search("^(\t*)  (```)", line)
        if parent_code_block is not None:
            return LineType.CODE_BLOCK_MARKER, LineHierarchy.PARENT
        if child_code_block is not None:
            return LineType.CODE_BLOCK_MARKER, LineHierarchy.CHILD
        # if no code block detected, could just be a line starting with "`"
        if L1_tag == "-":
            return LineType.LIST, LineHierarchy.PARENT
        elif L1_tag == " ":
            return LineType.TEXT, LineHierarchy.CHILD
        else:
            print("PARSING ERROR AT LINE:", line)
            exit(1)
    else:
        # no tag recognized, must be text.
        if L1_tag == "-":
            return LineType.LIST, LineHierarchy.PARENT
        # no L1_tag, must be part of a multi-line content
        else:
            return LineType.TEXT, LineHierarchy.CHILD


target_line_indent = 0
cur_list_depth = 0
last_target_line_indent = 0
traversing_code_block = False

lines = []

for line in lines_raw:
    # match any line and get its indentation level
    line_re = re.search("^(\t*)(.*)$", line)

    if line_re is None:
        print("ERROR: no match on:", line)
        continue

    line_content_raw = line_re.groups()[1]
    line_indent = len(line_re.groups()[0])
    line_type, line_hierarchy = get_line_type(line)
        
    lines.append(
        {
            "content": line_content_raw,
            "indent" : line_indent,
            "type": line_type,
            "hierarchy": line_hierarchy
        }
    )


for i in range(len(lines)):

    print("[", lines[i]["indent"], lines[i]["type"], lines[i]["hierarchy"], "]", ":", lines[i]["content"])

    if lines[i]["type"] == LineType.CODE_BLOCK_MARKER:
        traversing_code_block = not traversing_code_block
    elif lines[i]["content"].find("../assets") >= 0:
        asset_re = re.search(r"(^.*\[.*\]\()(../)assets/(.*)\)", lines[i]["content"])
        if asset_re is not None:
            filename = asset_re.groups()[2]
            print("Importing asset:", filename)
            import_asset(filename)
            lines[i]["content"] = asset_re.groups()[0] + "assets/" + asset_re.groups()[2] + ")"
            
            # TODO make sure this need not to be handled down below as well.
    elif lines[i]["content"].find("{{renderer :drawio,") >= 0:
        asset_re = re.search(r"(^.*){{renderer :drawio, (.*.svg)}}", lines[i]["content"])
        if asset_re is not None:
            filename = asset_re.groups()[1]
            print("filename:", filename)
            print("Importing asset:", filename)
            import_asset(filename, subdir=os.path.join("storages", "logseq-drawio-plugin"))
            lines[i]["content"] = asset_re.groups()[0] + "!["+ filename +"]"+ "(assets/"+ filename +")"
            # TODO make sure this need not to be handled down below as well.

    # {{renderer :drawio, 1715330124268.svg}}

    # CALCULATE TARGET INDENTATION 
    if i == 0:
        target_line_indent = 0
    elif lines[i]["type"] == LineType.TITLE or lines[i-1]["type"] == LineType.TITLE:
        # Titles have no indentation. 
        # Any element that comes immediately after a title must have no indentation as well
        target_line_indent = 0
    elif lines[i]["type"] == LineType.CODE or lines[i]["type"] == LineType.CODE_BLOCK_MARKER:
        target_line_indent = last_target_line_indent

    if lines[i]["type"] != LineType.TITLE and lines[i-1]["type"] != LineType.TITLE:
        # If this row belongs to a series of rows of the same kind...
        if lines[i]["indent"] > lines[i-1]["indent"]:
            # Standard markdown list: the first level is not indented, the subsequents are.
            cur_list_depth += 1
            if cur_list_depth > 1:
                target_line_indent = last_target_line_indent + 1
            else:
                target_line_indent = last_target_line_indent
        elif lines[i]["indent"] < lines[i-1]["indent"]:
            # Detect if this LIST element is less indendeted than the previous 
            target_line_indent = last_target_line_indent - (lines[i-1]["indent"] - lines[i]["indent"])
            cur_list_depth -= 1
        else:
            target_line_indent = last_target_line_indent

    if traversing_code_block:
        content = lines[i]["content"][2:]
    else:
        # Represent each line depending on its type
        if lines[i]["type"] == LineType.TITLE:
            content = lines[i]["content"][lines[i]["content"].find("#"):]
            cur_list_depth = 0
        elif lines[i]["type"] == LineType.LIST:
            if cur_list_depth > 0:
                content = lines[i]["content"]
                if lines[i+1]["indent"] < lines[i]["indent"]:
                    content = content + "\n"
            else:
                if i < len(lines)-1 and i < len(lines)-1 and lines[i+1]["type"] == LineType.LIST and lines[i+1]["indent"] == lines[i]["indent"]:
                    content = lines[i]["content"][2:] + "\\"
                else:
                    content = lines[i]["content"][2:]
        elif lines[i]["type"] == LineType.TEXT:
            if lines[i]["content"].find("collapsed:: true") >= 0:
                print("Removing logseq-specifc tag:", lines[i]["content"])
                continue
            else:
                # We might be in a multi-line content block of some kind.
                content = lines[i]["content"][2:]
            # always terminate the line with a return
            if i < len(lines)-1 and lines[i+1]["type"] != lines[i]["type"]:
                content = content + "\n"
        elif lines[i]["type"] == LineType.CODE:
            content = lines[i]["content"][2:]
        elif lines[i]["type"] == LineType.EMPTY:
            content = "<br>\n"
        elif lines[i]["type"] == LineType.CODE_BLOCK_MARKER:
            content = lines[i]["content"][2:]
        elif lines[i]["type"] == LineType.QUOTE:
            content = lines[i]["content"][2:]

        if lines[i]["type"] != LineType.CODE_BLOCK_MARKER:
            if i < len(lines)-1 and lines[i+1]["type"] == LineType.TEXT and not lines[i]["type"] == LineType.TITLE:
                content = content + "\\"

    content = content + "\n"

    print("last_target_line_indent:", last_target_line_indent, "target_line_indent:", target_line_indent)
    print("cur_list_depth:", cur_list_depth)

    tabs = "".join(["\t" for _ in range(target_line_indent)])
    content = tabs + content
    # only update previous element type for next cycle when a new element starts
    if line_hierarchy == LineHierarchy.PARENT:
        last_target_line_indent = target_line_indent

    print("")

    out.write(content)