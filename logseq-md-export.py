import re
from enum import Enum

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

file = open("sample.md", "r")
lines = file.readlines()
out = open("out.md", "w")

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


last_parent_type = LineType.LIST
last_line_indent = 0
target_line_indent = 0
status = State.CLEAR
cur_list_depth = 0
last_target_line_indent = 0
i = 0

for line in lines:
    # match any line and get its indentation level
    line_re = re.search("^(\t*)(.*)$", line)
    
    if line_re is None:
        print("ERROR: no match on:", line)
        continue
    
    line_content_raw = line_re.groups()[1]
    line_indent = len(line_re.groups()[0])
    line_type, line_hierarchy = get_line_type(line)
        
    print("[", line_indent, line_type, line_hierarchy, "]", ":", line_content_raw)

    if line_type != LineType.CODE_BLOCK_MARKER and status == State.TRAVERSING_CODE_BLOCK:
        line_type = LineType.CODE

    if i == 0:
        last_parent_type = line_type        

    # CALCULATE TARGET INDENTATION AND UPDATE STATUS
    if last_parent_type == LineType.TITLE:
        # Titles have no indentation. 
        # Any element that comes immediately after a title must have no indentation as well
        target_line_indent = 0
    elif last_parent_type == line_type or line_hierarchy == LineHierarchy.CHILD:
        # If this row belongs to a series of row of the same kind...
        if line_indent > last_line_indent:
            # Standard markdown list: the first level is not indented, the subsequents are.
            if line_type != LineType.CODE_BLOCK_MARKER or line_type != LineType.CODE:
                cur_list_depth += 1
                if cur_list_depth > 1:
                    target_line_indent = last_target_line_indent + 1
                    print("cacca", line_type)
                else:
                    target_line_indent = last_target_line_indent
        elif line_indent < last_line_indent:
            # Detect if this LIST element is less indendeted than the previous 
            target_line_indent = last_target_line_indent - (last_line_indent - line_indent)
            cur_list_depth -= 1
        else:
            target_line_indent = last_target_line_indent

    # Represent each line depending on its type
    if line_type == LineType.TITLE:
        content = line[line.find("#"):]
        last_line_indent = 0
        target_line_indent = 0
        cur_list_depth = 0
    elif line_type == LineType.LIST:
        if cur_list_depth > 0:
            content = line[line.find("-"):]  # TODO re-evaluate correctness of IF / ELSE action
        else:
            content = line[line.find("-")+2:-1] + "<br>\n"
    elif line_type == LineType.TEXT:
        # We might be in a multi-line content block of some kind.
        # content = line[3:]
        content = line_content_raw[2:] + "\n"
        if last_parent_type == LineType.QUOTE:
            # we are in a multi-line quote block.
            content = "\\\n" + line_content_raw[2:]
    elif line_type == LineType.CODE:
        target_line_indent = last_target_line_indent
        content = line_content_raw[2:] + "\n"
    elif line_type == LineType.EMPTY:
        content = "<br><br>\n"
    elif line_type == LineType.CODE_BLOCK_MARKER:
        target_line_indent = last_target_line_indent
        if status == State.TRAVERSING_CODE_BLOCK:
            status = State.CLEAR
        else:
            status = State.TRAVERSING_CODE_BLOCK
        content = line[line.find("`"):] # TODO substitute all line.find() with line_content_raw[idx:]
    elif line_type == LineType.QUOTE:
        content = line_content_raw[2:]
    else:
        content = line

    print("last_parent_type:", last_parent_type, "last_line_indent:", last_line_indent, "last_target_line_indent:", last_target_line_indent, "target_line_indent:", target_line_indent)
    print("status:", status)
    print("cur_list_depth:", cur_list_depth)

    tabs = "".join(["\t" for _ in range(target_line_indent)])
    content = tabs + content
    # only update previous element type for next cycle when a new element starts
    if line_hierarchy == LineHierarchy.PARENT:
        last_parent_type = line_type
        last_line_indent = line_indent
        last_target_line_indent = target_line_indent

    i += 1
    if i > 120:
        exit(0)
    print("")

    out.write(content)