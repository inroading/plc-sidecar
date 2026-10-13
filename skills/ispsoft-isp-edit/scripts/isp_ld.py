"""Byte-preserving helpers for LD patterns observed in ISPSoft 3.24 projects.

These constructors do not prove that ISPSoft accepts or compiles a generated LD
network. Inspect a known-good network of the target PLC family before reuse.
"""

from __future__ import annotations

import re

EOL = b"\r\n"


def _line(value: str) -> bytes:
    if "\r" in value or "\n" in value:
        raise ValueError("LD field must fit on one line")
    return value.encode("ascii")


def lines(*values: str) -> bytes:
    return EOL.join(_line(value) for value in values) + EOL


def node(*fields: str) -> bytes:
    return lines("[LD_NODE]", *fields, "[END_LD_NODE]")


def contact(device: str, kind: str = "normal") -> bytes:
    types = {"normal": 1, "closed": 2, "rising": 3}
    return node(f"TYPE={types[kind]}", f"DEV_NAME={device}")


def comparison_equal(left: str, right: str) -> bytes:
    return (
        node("TYPE=11", "<VAR_NODE_S>", f"VAR_NAME={left}", f"VAR_NAME={right}", "<VAR_NODE_E>")
        + node("TYPE=10", "SYMB==", "DEV_NAME=", "API_NUM=-1")
        + node("TYPE=12")
        + node("TYPE=7")
    )


def coil(device: str, kind: str = "out") -> bytes:
    types = {"out": 13, "set": 15, "reset": 16}
    return node(f"TYPE={types[kind]}", f"DEV_NAME={device}")


def instruction(name: str, api_num: int, inputs: list[str], output: str | None = None) -> bytes:
    if api_num < 0 or not inputs:
        raise ValueError("Instruction requires a nonnegative API number and operands")
    body = node(
        "TYPE=11", "<VAR_NODE_S>",
        *(f"VAR_NAME={value}" for value in inputs),
        "<VAR_NODE_E>",
    )
    body += node("TYPE=9", f"SYMB={name}", "DEV_NAME=", f"API_NUM={api_num}")
    if output is None:
        body += node("TYPE=12")
    else:
        body += node("TYPE=12", "<VAR_NODE_S>", f"VAR_NAME={output}", "<VAR_NODE_E>")
    return body + node("TYPE=7")


def network(number: int, roots: list[bytes], result: bytes, comment: str = "") -> bytes:
    if number < 0:
        raise ValueError("NET_ID must be nonnegative")
    return (
        lines(
            "<NETWORK_START>", "<PROPERTIES_START>", f"NET_ID={number}",
            "NET_LABEL=", "NET_ACTIVE=TRUE", "NET_BOOKMARK=FALSE",
            "NET_MODIFY=FALSE", "NET_FOLD=FALSE", "(*", comment,
            "*)", "<PROPERTIES_END>", "<ROOTLINK_START>",
        )
        + b"".join(roots)
        + lines("<ROOTLINK_END>", "<OUTLINK_START>")
        + result
        + lines("<OUTLINK_END>", "<NETWORK_END>")
    )


def pou_block(project: bytes, name: str) -> bytes:
    escaped = re.escape(_line(name))
    pattern = rb"<POU>\r\nP_Name=" + escaped + rb"\r\n.*?</POU>\r\n"
    matches = list(re.finditer(pattern, project, re.S))
    if len(matches) != 1:
        raise ValueError(f"Expected one POU named {name}, found {len(matches)}")
    return matches[0].group()


def replace_pou(project: bytes, name: str, replacement: bytes) -> bytes:
    original = pou_block(project, name)
    if not replacement.startswith(lines("<POU>", f"P_Name={name}")) or not replacement.endswith(lines("</POU>")):
        raise ValueError("Replacement does not contain the expected complete POU")
    return project.replace(original, replacement, 1)


def replace_network(project: bytes, pou_name: str, net_id: int, replacement: bytes) -> bytes:
    pou = pou_block(project, pou_name)
    networks = re.findall(rb"<NETWORK_START>.*?<NETWORK_END>\r\n", pou, re.S)
    target = [network for network in networks if re.search(rb"(?:^|\r\n)NET_ID=" + str(net_id).encode() + rb"\r\n", network)]
    if len(target) != 1:
        raise ValueError(f"Expected one network {net_id} in {pou_name}, found {len(target)}")
    if not replacement.startswith(lines("<NETWORK_START>")) or not replacement.endswith(lines("<NETWORK_END>")):
        raise ValueError("Replacement is not a complete network")
    updated = pou.replace(target[0], replacement, 1)
    return replace_pou(project, pou_name, updated)
