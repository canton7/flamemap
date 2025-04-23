import subprocess
import re
import sys
from pathlib import Path
import argparse


class ElfFlameGenerator:
    def __init__(self, section_categories, root_dirs, nm, readelf):
        if not section_categories:
            section_categories = {
                "flash": [".text", ".data", ".rodata"],
                "ram": [".bss", ".data"],
            }

        self._section_categories = section_categories
        self._root_dirs = root_dirs
        self._nm = nm
        self._readelf = readelf

    def _add_symbol_to_tree(self, tree, symbol, name, path_parts):
        section = symbol["section"]
        category = next((k for k, v in self._section_categories.items() if section in v), None)
        if not category:
            print(f"Found unmapped section: {section}. Specify mapping with -s", file=sys.stderr)
            return

        node = tree[category]
        for part in path_parts:
            child = node.get(part)
            if not child:
                child = {}
                node[part] = child
            node = child
        file_node = node.setdefault(section, {})
        file_node[name] = symbol["size"]

    def generate(self, elf, static_libraries, output):
        sections = {}
        symbols = {}

        with subprocess.Popen(
            [self._readelf, "--symbols", "--wide", "--sym-base=10", elf], stdout=subprocess.PIPE
        ) as p:
            for line in p.stdout:
                match = re.fullmatch(
                    r"\s*(\d+):\s+(?P<addr>\w+)\s+(?P<size>\d+)\s+(?P<type>\w+)\s+(?P<bind>\w+)\s+(?P<vis>\w+)\s+(?P<ndx>\w+)\s+(?P<name>.+)",
                    line.decode("utf-8").strip(),
                )
                if not match:
                    continue

                # All of the sections should appear before anything else
                if match["type"] == "SECTION":
                    sections[match["ndx"]] = match["name"]
                elif match["size"] != "0":
                    symbols[(match["name"], match["addr"])] = {
                        "section": sections[match["ndx"]],
                        "size": int(match["size"]),
                        "found_in_nm": False,
                    }

        tree = {}
        for category in self._section_categories:
            tree[category] = {}

        with subprocess.Popen(
            [self._nm, "--line-numbers", "--print-file-name", elf, *static_libraries], stdout=subprocess.PIPE
        ) as p:
            for line in p.stdout:
                match = re.fullmatch(
                    r"(?P<infile>[^:]+):(?:(?P<object>[^:]+):)?(?P<addr>\w+)\s+(?P<section>\w+)\s+(?P<name>\S+)(?:\s+(?P<file>.+?):(?P<line>\d+))?",
                    line.decode("utf-8").strip(),
                )
                if not match:
                    continue

                symbol = symbols.get((match["name"], match["addr"]))
                if not symbol:
                    continue

                # If it doesn't have a file path, then use the library / object name (if it exists) as the path
                if match["file"]:
                    path_parts = Path(match["file"]).resolve().parts
                elif match["infile"] != elf:
                    path_parts = list(Path(match["infile"]).resolve().parts)
                    if match["object"]:
                        path_parts.append(match["object"])
                else:
                    continue

                symbol["found_in_nm"] = True

                # If any root dir appear in this path, then strip everything before it
                for root_dir in self._root_dirs:
                    if root_dir in path_parts:
                        path_parts = path_parts[path_parts.index(root_dir) :]

                self._add_symbol_to_tree(tree, symbol, match["name"], path_parts)

        for (name, _), symbol in symbols.items():
            if not symbol["found_in_nm"]:
                self._add_symbol_to_tree(tree, symbol, name, ["<unknown>"])

        def _visit_node(items, path):
            for name, node in items:
                node_path = [*path, name]
                if isinstance(node, int):
                    yield (node_path, node)
                else:
                    yield from _visit_node(sorted(node.items()), node_path)

        elf_name = Path(elf).name
        for path, size in _visit_node(tree.items(), []):
            output.write(f"{elf_name};" + ";".join(path) + f" {size}\n")


class ParseDict(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        d = getattr(namespace, self.dest) or {}

        if values:
            for item in values:
                key, value = item.split("=", 1)
                d[key] = value.split(",")

        setattr(namespace, self.dest, d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="flame-map",
        description="Renders flash/ram usage, derived from a .elf file, as a flame graph",
    )
    parser.add_argument("file", metavar="file.elf", help="Path to the elf to process")
    parser.add_argument(
        "-o", "--output", type=argparse.FileType("w"), default=sys.stdout, help="File to write to (defaults to stdout)"
    )
    parser.add_argument(
        "-a",
        "--library",
        metavar="STATIC_LIBRARY",
        dest="libraries",
        action="append",
        default=[],
        help="Specify additional static libraries to find symbols in",
    )
    parser.add_argument(
        "-s",
        "--section",
        metavar="name=sec1,sec2",
        nargs="+",
        dest="sections",
        action=ParseDict,
        default={},
        help="Add rules for grouping sections into flash/ram/etc",
    )
    parser.add_argument(
        "-r",
        "--root",
        metavar="ROOT",
        dest="roots",
        action="append",
        default=[],
        help="Add folders which are considered root folders",
    )
    parser.add_argument("--nm", default="nm", help="Path to nm.exe")
    parser.add_argument("--readelf", default="readelf", help="Path to readelf.exe")

    args = parser.parse_args()

    generator = ElfFlameGenerator(args.sections, args.roots, args.nm, args.readelf)
    generator.generate(args.file, args.libraries, args.output)
