#!/usr/bin/env python3
"""Inspect and repack the ISPSoft raw-DEFLATE .isp variant described in the skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from isp_ld import pou_block, replace_pou


class UnsupportedFormat(ValueError):
    pass


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def deflate(payload: bytes, level: int) -> bytes:
    compressor = zlib.compressobj(level, wbits=-15)
    return compressor.compress(payload) + compressor.flush()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Project:
    original: bytes
    start: int
    block_size: int
    payload: bytes
    compressed: bytes
    trailer: bytes
    compression_level: int | None
    has_end_field: bool
    has_length_field: bool

    @classmethod
    def parse(cls, data: bytes) -> Project:
        if len(data) < 0x9C:
            raise UnsupportedFormat("File is too short for the observed header")
        start, size = u32(data, 0x98), u32(data, 0x94)
        end = start + size
        if start < 0x9C or size < 6 or end > len(data):
            raise UnsupportedFormat("Compressed block offset or size is invalid")
        if data[start : start + 2] != b"\x08\x00":
            raise UnsupportedFormat("Unknown compressed-block marker")
        compressed = data[start + 6 : end]
        try:
            inflater = zlib.decompressobj(-15)
            payload = inflater.decompress(compressed)
            payload += inflater.flush()
        except zlib.error as error:
            raise UnsupportedFormat(f"Raw DEFLATE decode failed: {error}") from error
        if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
            raise UnsupportedFormat("Compressed data has an invalid end or extra bytes")
        if not payload.startswith(b"<PROJECT>\r\n"):
            raise UnsupportedFormat("Unexpected project payload signature")
        if zlib.crc32(payload) != u32(data, start + 2):
            raise UnsupportedFormat("Payload CRC32 mismatch")
        header_end, header_length = u32(data, 0x58), u32(data, 0x7C)
        if header_end not in (0, end):
            raise UnsupportedFormat("Unknown nonzero compressed-end header field")
        if header_length not in (0, len(payload)):
            raise UnsupportedFormat("Unknown nonzero payload-length header field")
        levels = [level for level in range(10) if deflate(payload, level) == compressed]
        return cls(
            original=data,
            start=start,
            block_size=size,
            payload=payload,
            compressed=compressed,
            trailer=data[end:],
            compression_level=min(levels) if levels else None,
            has_end_field=header_end != 0,
            has_length_field=header_length != 0,
        )

    def repack(self, payload: bytes) -> bytes:
        if self.compression_level is None:
            raise UnsupportedFormat("Original cannot be reproduced byte-for-byte; repacking refused")
        validate_payload(payload)
        compressed = deflate(payload, self.compression_level)
        new_size = len(compressed) + 6
        header = bytearray(self.original[: self.start])
        struct.pack_into("<I", header, 0x94, new_size)
        if self.has_end_field:
            struct.pack_into("<I", header, 0x58, self.start + new_size)
        if self.has_length_field:
            struct.pack_into("<I", header, 0x7C, len(payload))
        result = (
            bytes(header)
            + b"\x08\x00"
            + struct.pack("<I", zlib.crc32(payload))
            + compressed
            + self.trailer
        )
        decoded = Project.parse(result)
        if decoded.payload != payload or decoded.trailer != self.trailer:
            raise UnsupportedFormat("New file failed read-back verification")
        if payload == self.payload and result != self.original:
            raise UnsupportedFormat("Unchanged project did not round-trip byte-for-byte")
        return result


def validate_payload(payload: bytes) -> None:
    if not payload.startswith(b"<PROJECT>\r\n") or b"</PROJECT>\r\n" not in payload:
        raise UnsupportedFormat("Edited payload has no complete PROJECT section")
    for opening, closing in (
        (b"<TASK>", b"</TASK>"),
        (b"<POU>", b"</POU>"),
        (b"<NETWORK_START>", b"<NETWORK_END>"),
        (b"[LD_NODE]", b"[END_LD_NODE]"),
    ):
        if payload.count(opening) != payload.count(closing):
            raise UnsupportedFormat(f"Mismatched {opening.decode('ascii')} blocks")
    pou_blocks = re.findall(rb"<POU>\r\n.*?</POU>\r\n", payload, re.S)
    if len(pou_blocks) != payload.count(b"<POU>"):
        raise UnsupportedFormat("Malformed POU boundaries")
    for pou in pou_blocks:
        name = re.search(rb"(?:^|\r\n)P_Name=([^\r\n]+)", pou)
        if name is None:
            raise UnsupportedFormat("POU is missing P_Name")
        networks = re.findall(rb"<NETWORK_START>.*?<NETWORK_END>", pou, re.S)
        for network in networks:
            matches = re.findall(rb"(?:^|\r\n)NET_ID=([^\r\n]+)", network)
            if len(matches) != 1:
                raise UnsupportedFormat(f"POU {name.group(1)!r} has a network without one NET_ID")


def summary(path: Path, project: Project) -> dict:
    payload = project.payload
    page = re.search(rb"(?:^|\r\n)Active_CodePage=([^\r\n]*)", payload)
    name = re.search(rb"(?:^|\r\n)Prj_Name=([^\r\n]*)", payload)
    tasks = re.findall(rb"(?:^|\r\n)T_PName=([^\r\n]*)", payload)
    codepage = page.group(1).decode("ascii", "replace") if page else None
    encoding = f"cp{codepage}" if codepage and codepage.isdigit() else "ascii"
    try:
        project_name = name.group(1).decode(encoding, "replace") if name else None
    except LookupError:
        project_name = name.group(1).decode("ascii", "replace") if name else None
    pous = []
    for block in re.findall(rb"<POU>\r\n.*?</POU>\r\n", payload, re.S):
        match = re.search(rb"(?:^|\r\n)P_Name=([^\r\n]*)", block)
        pous.append({
            "name": match.group(1).decode("ascii", "replace") if match else "?",
            "networks": block.count(b"<NETWORK_START>"),
        })
    return {
        "path": str(path.resolve()),
        "sha256": sha256(project.original),
        "file_bytes": len(project.original),
        "block_start": project.start,
        "block_size": project.block_size,
        "trailer_bytes": len(project.trailer),
        "payload_bytes": len(payload),
        "payload_crc32": f"{zlib.crc32(payload):08x}",
        "roundtrip_level": project.compression_level,
        "project_name": project_name,
        "active_codepage": codepage,
        "task_pous": [value.decode("ascii", "replace") for value in tasks],
        "pous": pous,
    }


def new_file(path: Path, data: bytes, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path} (use --overwrite if intended)")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as temporary:
        temporary.write(data)
        temporary_name = Path(temporary.name)
    try:
        if path.exists() and not overwrite:
            raise FileExistsError(f"Output already exists: {path}")
        os.replace(temporary_name, path)
    finally:
        temporary_name.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "extract", "pack", "extract-pou", "replace-pou"):
        item = commands.add_parser(command)
        item.add_argument("source", type=Path)
        if command == "extract":
            item.add_argument("payload", type=Path)
        if command == "pack":
            item.add_argument("payload", type=Path)
            item.add_argument("output", type=Path)
        if command == "extract-pou":
            item.add_argument("name")
            item.add_argument("pou", type=Path)
        if command == "replace-pou":
            item.add_argument("name")
            item.add_argument("pou", type=Path)
            item.add_argument("output", type=Path)
        if command != "inspect":
            item.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    project = Project.parse(args.source.read_bytes())
    if args.command == "inspect":
        validate_payload(project.payload)
        result = summary(args.source, project)
    elif args.command == "extract":
        if args.source.resolve() == args.payload.resolve():
            raise ValueError("Payload path must differ from source project")
        new_file(args.payload, project.payload, args.overwrite)
        result = {"payload_path": str(args.payload.resolve()), **summary(args.source, project)}
    elif args.command == "extract-pou":
        if args.source.resolve() == args.pou.resolve():
            raise ValueError("POU path must differ from source project")
        new_file(args.pou, pou_block(project.payload, args.name), args.overwrite)
        result = {"pou_path": str(args.pou.resolve()), "pou_name": args.name, **summary(args.source, project)}
    else:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("In-place .isp modification is refused; choose a new output path")
        if args.command == "replace-pou":
            edited = replace_pou(project.payload, args.name, args.pou.read_bytes())
        else:
            edited = args.payload.read_bytes()
        updated = project.repack(edited)
        new_file(args.output, updated, args.overwrite)
        result = {"output_path": str(args.output.resolve()), **summary(args.output, Project.parse(updated))}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, struct.error) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(2)
