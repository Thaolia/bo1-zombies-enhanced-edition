#!/usr/bin/env python3
"""Pack the native BO2 maps' colour maps (bo2_bsp.py's <out>/images/*.iwi, gathered in <game>/main/images/) into one
IWD, the zip BO1 reads its own images from (main/iw_XX.iwd), instead of 1 300 loose files.

    tools/bo2/bo2_iwd.py <images dir> <out.iwd> [--pattern 'bo2_*.iwi']

Each image goes in as images/<name>.iwi, deflated (25 % smaller on the four maps' images, as retail's IWDs are),
sorted by name with a fixed date, so the same images always give the same bytes. In main/ the engine takes only an
IWD whose name starts with "iw_" (com_files.cpp, "Invalid IWD"): name it main/iw_bo2maps.iwd. Prints the image count.
"""
import argparse
import fnmatch
import os
import sys
import zipfile

FIXED_DATE = (2026, 1, 1, 0, 0, 0)


def pack(images, out, pattern="bo2_*.iwi"):
    """Writes out from the images matching pattern in images; returns their names, sorted."""
    names = sorted(n for n in os.listdir(images) if fnmatch.fnmatch(n, pattern)
                   and os.path.isfile(os.path.join(images, n)))
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in names:
            info = zipfile.ZipInfo("images/" + name, FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(images, name), "rb") as f:
                z.writestr(info, f.read())
    os.replace(tmp, out)
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", help="the folder holding the .iwi files")
    parser.add_argument("out", help="the IWD to write (main/iw_bo2maps.iwd)")
    parser.add_argument("--pattern", default="bo2_*.iwi", help="which files go in (default: bo2_*.iwi)")
    args = parser.parse_args(argv)
    names = pack(args.images, args.out, args.pattern)
    if not names:
        print(f"{args.images}: no {args.pattern}", file=sys.stderr)
        os.remove(args.out)
        return 1
    print(f"{args.out}: {len(names)} images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
