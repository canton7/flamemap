flamemap
========

Flamemap is a tool to generate flame graphs show flash and RAM usage for embedded systems.
Flame graphs are a very good way to see at a glance where your space is being used, and dig into areas of interest.

It uses the debug info in your .elf file to work out how much space each symbol takes, and which file defines each
symbol. It then generates a file which can be loaded into a flame graph viewer.


Usage
-----

You will need:
  1. An .elf file containing your application, containing DWARF debug information, e.g. generated with `-g3`
  2. `readelf` and `nm` available

At the most basic, run:

```sh
python flame-map.py YourProject.elf -o flame.graph
```

This generates the file `flame.graph` in "folded format", which can be consumed by tools such as Brendan Gregg's
[orignal flame graph tool](https://www.brendangregg.com/flamegraphs.html), as well as online tools such as
[speedscope.io](https://www.speedscope.app/).

The flame graph stacks show, in order:
  1. The region, flash/ram
  2. The path to each source file, grouped by directory
  3. The section which is being used by each symbol (e.g. `.bss`, `.data`)
  4. The symbols themselves


### Root folders

Be default, the full filesystem path to each file is shown.
You can specify one or more root folders, and any parts of a file path which appear before that root folder are ignored.
For example, if a file has the path `/data/Jenkins/MyProject/Source/Foo/Bar.c`, you can pass `-r Source`, and the path
will be rendered as `Source/Foo/Bar.c`.
You can pass multiple roots if you want, which can be useful if you use static libraries.


### Section to group mapping

Flamemap has a default mapping from linker sections to flash/ram groups, but you map want to customise this, e.g. if you
have custom sections.
You can do this with the `-s` flag, which has the format `-s group=.section1,section2`.
The default is `-s flash=.text,.data,.rodata -s ram=.bss,.data`.
Any symbols in sections which are not mapped to a group will be ignored.


### Static libraries

If your code references a static library, and debug information for symbols in that static library isn't contained in=
your .elf, then these will appear in a section called `<unknown>`.
To resolve this, you can pass the static libraries to flamemap with `-a Path/To/Archive.a`, and flamemap will search
those for symbol locations.


### Paths to `readelf` and `nm`

If `readelf` and `nm` aren't on your PATH, you can pass the full paths to these with `--readelf` and `--nm`.
